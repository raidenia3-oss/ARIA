import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/message.dart';
import '../models/pc_state.dart';
import '../models/task.dart';
import 'notification_service.dart';
import 'offline_queue.dart';
import 'settings_service.dart';

/// Transport state of the `/ws` connection.
/// Spec: v6/MOBILE_SYNC_SPEC.md §1.2.
enum ConnectionState {
  disconnected,
  connecting,
  connected,
  degraded,
  backoff,
}

/// Result of a backend call. Never throws for protocol-level failures.
class BackendResult<T> {
  const BackendResult.ok(this.value)
      : error = null,
        httpStatus = 200,
        retryAfterSeconds = null;
  const BackendResult.err(this.error, {this.httpStatus, this.retryAfterSeconds})
      : value = null;

  final T? value;
  final String? error;
  final int? httpStatus;
  final int? retryAfterSeconds;

  bool get isOk => error == null && value != null;

  /// The POC handlers return HTTP 200 with an in-body `status: "error"`, so a
  /// 2xx is not sufficient (spec §4.8).
  bool get bodyReportedError =>
      value is Map && (value as Map)['status'] == 'error';

  @override
  String toString() => 'BackendResult(ok: $isOk, error: $error, status: $httpStatus)';
}

/// Axum REST + WebSocket client.
///
/// Spec: v6/MOBILE_SYNC_SPEC.md §4 (REST) and §1–§3 (WebSocket).
class BackendService extends ChangeNotifier {
  BackendService({
    required this.settings,
    required this.queue,
    required this.notifications,
  });

  final SettingsService settings;
  final OfflineQueue queue;
  final NotificationService notifications;

  static const String cacheBoxName = 'airi_cache';
  static const String logBoxName = 'airi_log';
  static const int maxLogEntries = 500;

  late final Dio _dio;
  late final Box _cache;
  late final Box _log;

  final StreamController<Message> _messages = StreamController<Message>.broadcast();
  Stream<Message> get messages => _messages.stream;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _channelSub;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  Timer? _pollTimer;
  int _attempt = 0;
  DateTime? _connectedAt;
  int _lastSeq = 0;

  ConnectionState _state = ConnectionState.disconnected;
  PcStateSnapshot _snapshot = const PcStateSnapshot();
  String _lastError = '';
  DateTime? _lastSyncAt;
  final List<String> _pendingAlerts = [];

  ConnectionState get state => _state;
  PcStateSnapshot get snapshot => _snapshot;
  String get lastError => _lastError;
  DateTime? get lastSyncAt => _lastSyncAt;
  bool get isConnected => _state == ConnectionState.connected;
  DateTime? get connectedAt => _connectedAt;
  List<String> get pendingAlerts => List.unmodifiable(_pendingAlerts);

  // --- Lifecycle ----------------------------------------------------------

  Future<void> init() async {
    await Hive.initFlutter();
    _cache = await Hive.openBox(cacheBoxName);
    _log = await Hive.openBox(logBoxName);

    _dio = Dio(
      BaseOptions(
        baseUrl: settings.effectiveBaseUrl,
        connectTimeout: const Duration(seconds: 6),
        // /api/chat proxies Ollama with a 60 s server-side timeout; the client
        // must outlive it or it aborts first (spec §4.5).
        receiveTimeout: const Duration(seconds: 70),
        sendTimeout: const Duration(seconds: 10),
        responseType: ResponseType.json,
        headers: {'Content-Type': 'application/json'},
      ),
    )..interceptors.add(
          InterceptorsWrapper(
            onRequest: (options, handler) {
              final token = settings.authToken;
              if (token.isNotEmpty) {
                options.headers['Authorization'] = 'Bearer $token';
              }
              options.headers['X-Idempotency-Key'] ??=
                  options.extra['idempotencyKey'] as String?;
              options.extra.remove('idempotencyKey');
              handler.next(options);
            },
          ),
        );

    _loadCache();
    if (settings.autoConnect) {
      connect();
    } else {
      _startPolling();
    }
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    _pollTimer?.cancel();
    _channelSub?.cancel();
    _channel?.sink.close();
    _messages.close();
    super.dispose();
  }

  void _setState(ConnectionState next, {String error = ''}) {
    if (_state == next && _lastError == error) return;
    _state = next;
    _lastError = error;
    notifyListeners();
  }

  void _log(String level, String message) {
    final entry = LogEntry(
      ts: DateTime.now(),
      level: level,
      message: message.length > LogEntry.maxMessageLength
          ? message.substring(0, LogEntry.maxMessageLength)
          : message,
    );
    _log.add(entry.ts.millisecondsSinceEpoch.toString() + entry.message.hashCode.toString());
    if (_log.length > maxLogEntries) {
      final keys = _log.keys.toList()..sort();
      for (final k in keys.take(_log.length - maxLogEntries)) {
        _log.delete(k);
      }
    }
  }

  List<LogEntry> recentLogs({int limit = 100}) {
    final entries = _log.values
        .whereType<Map>()
        .map((e) => LogEntry.fromJson(e.cast<String, dynamic>()))
        .toList()
      ..sort((a, b) => b.ts.compareTo(a.ts));
    return entries.take(limit).toList();
  }

  // --- Cache --------------------------------------------------------------

  void _loadCache() {
    final raw = _cache.get('pc_state');
    if (raw is String) {
      try {
        _snapshot = PcStateSnapshot.fromJson(
            jsonDecode(raw).map((k, v) => MapEntry(k.toString(), v)));
        notifyListeners();
      } catch (_) {
        _log('warn', 'cache parse failed; starting cold');
      }
    }
  }

  Future<void> _persistCache() async {
    await _cache.put('pc_state', _snapshot.encode());
  }

  void _updateSnapshot(PcStateSnapshot next) {
    _snapshot = next.copyWith(capturedAt: DateTime.now());
    _lastSyncAt = DateTime.now();
    unawaited(_persistCache());
    notifyListeners();
  }

  // --- WebSocket ----------------------------------------------------------

  Future<void> connect() async {
    if (_state == ConnectionState.connecting || _state == ConnectionState.connected) return;
    _reconnectTimer?.cancel();
    _setState(ConnectionState.connecting);

    final uri = Uri.tryParse(_wsUrl);
    if (uri == null) {
      _setState(ConnectionState.disconnected, error: 'Invalid base URL');
      return;
    }

    try {
      // pingInterval drives RFC 6455 control-frame pings. web_socket_channel
      // reconnects the URL after replacing websocket_client; the deprecated
      // package could not send them (spec §8).
      final channel = IOWebSocketChannel.connect(
        uri,
        pingInterval: const Duration(seconds: 30),
        connectTimeout: const Duration(seconds: 8),
        headers: settings.authToken.isEmpty
            ? null
            : {'Authorization': 'Bearer ${settings.authToken}'},
      );
      await channel.ready;
      _channel = channel;
      _attempt = 0;
      _connectedAt = DateTime.now();
      _setState(ConnectionState.connected);

      _channelSub = channel.stream.listen(
        _onFrame,
        onDone: _onDisconnected,
        onError: (Object e) => _onDisconnected(error: e.toString()),
        cancelOnError: true,
      );

      _sendRaw(Message.identifyFrame(
        deviceId: settings.deviceId,
        platform: Platform.operatingSystem,
      ));
      _sendRaw(Message.subscribeFrame(settings.channels));
      _startAppPing();
      _stopPolling();
      _log('info', 'ws connected: ${_wsUrl}');

      if (settings.replayOnReconnect) {
        unawaited(replayQueue());
      }
      unawaited(refreshAll());
    } catch (e) {
      _log('warn', 'ws connect failed: $e');
      _scheduleReconnect();
    }
  }

  String get _wsUrl {
    final uri = Uri.parse(settings.effectiveBaseUrl);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    final token = settings.authToken;
    return uri
        .replace(scheme: scheme, path: '/ws', query: token.isEmpty ? '' : 'token=${Uri.encodeQueryComponent(token)}')
        .toString();
  }

  void _onFrame(dynamic raw) {
    final text = raw is String ? raw : utf8.decode(raw as List<int>, allowMalformed: true);
    final message = Message.tryParse(text);
    if (message == null) {
      _log('warn', 'unparseable frame: ${text.substring(0, text.length.clamp(0, 80))}');
      return;
    }
    if (message.seq != null) {
      if (message.hasSequenceGap(_lastSeq)) {
        _log('warn', 'sequence gap; forcing full resync');
        unawaited(refreshAll());
      }
      _lastSeq = message.seq!;
    }
    if (!_messages.isClosed) _messages.add(message);
    unawaited(_applyMessage(message));
  }

  Future<void> _applyMessage(Message message) async {
    switch (message.type) {
      case MessageType.connected:
        _connectedAt = DateTime.now();
        _setState(ConnectionState.connected);
        _log('info', 'welcome: ${message.connectedAgents.length} agents');
        break;
      case MessageType.heartbeat:
        final status = message.systemStatus;
        if (status != null) _updateSnapshot(_snapshot.copyWith(status: status));
        break;
      case MessageType.taskAvailable:
        final task = message.task;
        if (task != null) {
          await notifications.showPush(
            type: 'task_available',
            title: 'Tarea disponible',
            body: task.taskType.label,
            payload: task.toJson(),
          );
        }
        break;
      case MessageType.taskResult:
        final result = message.taskResult;
        if (result != null) {
          await notifications.showPush(
            type: 'task_result',
            title: 'Tarea completada',
            body: '${result.taskId}: ${result.status}',
            payload: result.toJson(),
          );
        }
        break;
      case MessageType.pcStateChange:
        final pc = message.pcState;
        if (pc != null) {
          _updateSnapshot(_snapshot.copyWith(pcState: pc));
          await notifications.showPush(
            type: 'pc_state_change',
            title: 'Estado del PC',
            body: pc.active ? 'Activo' : 'Inactivo',
            payload: pc.toJson(),
          );
        }
        break;
      case MessageType.systemAlert:
        final alert = message.alert;
        if (alert != null) {
          _pendingAlerts.add('${alert.code}: ${alert.message}');
          if (_pendingAlerts.length > 20) _pendingAlerts.removeAt(0);
          await notifications.showPush(
            type: 'system_alert',
            title: alert.isCritical ? 'ARIA — crítico' : 'ARIA — alerta',
            body: alert.message,
            payload: alert.toJson(),
          );
          notifyListeners();
        }
        break;
      case MessageType.subscribed:
        _log('info', 'subscribed: ${message.raw['channels']}');
        break;
      case MessageType.echo:
      case MessageType.ack:
      case MessageType.pong:
        break;
      case MessageType.error:
        _log('error', message.text ?? 'server error');
        break;
      case MessageType.unknown:
        _log('debug', 'unknown frame: ${message.raw['type']}');
        break;
    }
  }

  void _startAppPing() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _sendRaw(Message.appPingFrame());
    });
  }

  void _sendRaw(String frame) {
    try {
      _channel?.sink.add(frame);
    } catch (e) {
      _log('warn', 'send failed: $e');
    }
  }

  void _onDisconnected({String error = ''}) {
    _channelSub?.cancel();
    _channelSub = null;
    _channel = null;
    _connectedAt = null;
    _pingTimer?.cancel();
    _scheduleReconnect(error: error);
  }

  void _scheduleReconnect({String error = ''}) {
    // Reset the backoff only after a connection has held for a full minute.
    if (_connectedAt != null &&
        DateTime.now().difference(_connectedAt!).inSeconds >= 60) {
      _attempt = 0;
    }
    final delaySeconds = _backoffSeconds(_attempt++);
    _setState(ConnectionState.backoff, error: error);
    _log('info', 'reconnect in ${delaySeconds}s (attempt $_attempt)');
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: delaySeconds), connect);
    _startPolling();
  }

  /// 1s, 2s, 4s, 8s, then 30s capped, with +/-20% jitter (spec §1.4).
  static int _backoffSeconds(int attempt) {
    const base = [1, 2, 4, 8, 30];
    final seconds = base[attempt < base.length ? attempt : base.length - 1];
    final jitter = 1 + (((DateTime.now().microsecondsSinceEpoch % 401) - 200) / 1000);
    return (seconds * jitter).round().clamp(1, 60);
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    _channelSub?.cancel();
    _channelSub = null;
    _channel?.sink.close();
    _channel = null;
    _attempt = 0;
    _setState(ConnectionState.disconnected);
    _startPolling();
  }

  // --- Polling ------------------------------------------------------------

  void _startPolling() {
    if (_pollTimer != null) return;
    final seconds = settings.pollIntervalSeconds;
    _pollTimer = Timer.periodic(Duration(seconds: seconds), (_) => refreshAll());
    unawaited(refreshAll());
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  // --- REST calls ---------------------------------------------------------

  Future<BackendResult<Map<String, dynamic>>> _get(String path) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        path,
        options: Options(validateStatus: (s) => s != null && s < 500),
      );
      final body = res.data ?? const <String, dynamic>{};
      if (res.statusCode != null && res.statusCode! >= 400) {
        return BackendResult.err(
          body['error']?.toString() ?? 'HTTP ${res.statusCode}',
          httpStatus: res.statusCode,
          retryAfterSeconds: _retryAfter(res),
        );
      }
      return BackendResult.ok(body);
    } on DioException catch (e) {
      return BackendResult.err(
        _dioError(e),
        httpStatus: e.response?.statusCode,
        retryAfterSeconds: _retryAfter(e.response),
      );
    } catch (e) {
      return BackendResult.err(e.toString());
    }
  }

  Future<BackendResult<Map<String, dynamic>>> _post(
    String path, {
    Map<String, dynamic>? body,
    String? idempotencyKey,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        path,
        data: body ?? const <String, dynamic>{},
        options: Options(
          validateStatus: (s) => s != null && s < 500,
          extra: idempotencyKey == null ? null : {'idempotencyKey': idempotencyKey},
        ),
      );
      final data = res.data ?? const <String, dynamic>{};
      if (res.statusCode != null && res.statusCode! >= 400) {
        return BackendResult.err(
          data['error']?.toString() ?? 'HTTP ${res.statusCode}',
          httpStatus: res.statusCode,
          retryAfterSeconds: _retryAfter(res),
        );
      }
      return BackendResult.ok(data);
    } on DioException catch (e) {
      return BackendResult.err(
        _dioError(e),
        httpStatus: e.response?.statusCode,
        retryAfterSeconds: _retryAfter(e.response),
      );
    } catch (e) {
      return BackendResult.err(e.toString());
    }
  }

  /// Transport-level failure is the only case the offline queue may absorb
  /// (spec §5.2); a server that answered is never treated as offline.
  static String _dioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionError:
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return 'backend_offline';
      case DioExceptionType.badCertificate:
        return 'bad_certificate';
      case DioExceptionType.cancel:
        return 'cancelled';
      case DioExceptionType.badResponse:
        return (e.response?.data is Map)
            ? ((e.response!.data as Map)['error']?.toString() ??
                'HTTP ${e.response?.statusCode}')
            : 'HTTP ${e.response?.statusCode}';
      case DioExceptionType.unknown:
        return e.message ?? 'request failed';
    }
  }

  static int? _retryAfter(Response? response) {
    final header = response?.headers.value('retry-after');
    if (header != null) return int.tryParse(header);
    return null;
  }

  /// Reachability probe. Deliberately does not touch the connection state:
  /// a successful REST call says nothing about the `/ws` socket.
  Future<bool> ping() async => (await _get('/api/system/ping')).isOk;

  /// One dashboard refresh. Every call is independent: a failure leaves the
  /// previous value in the snapshot rather than blanking the UI.
  Future<void> refreshAll() async {
    final status = await _get('/api/system/status');
    if (status.isOk) {
      _updateSnapshot(_snapshot.copyWith(status: SystemStatus.fromJson(status.value!)));
    }

    final memory = await _get('/api/system/memory');
    if (memory.isOk) {
      _updateSnapshot(_snapshot.copyWith(memory: MemoryInfo.fromJson(memory.value!)));
    }

    // 404 until the backend adds it (spec §0.2.2) — leaves CpuInfo.unavailable.
    final cpu = await _get('/api/system/cpu');
    if (cpu.isOk) {
      _updateSnapshot(_snapshot.copyWith(cpu: CpuInfo.fromJson(cpu.value!)));
    }

    final agents = await _get('/api/agents/status');
    if (agents.isOk) {
      _updateSnapshot(_snapshot.copyWith(agents: AgentsStatus.fromJson(agents.value!)));
    }

    if (_budget.consume('host')) {
      final whois = await _get('/api/system/whois');
      if (whois.isOk) {
        _updateSnapshot(_snapshot.copyWith(host: HostInfo.fromJson(whois.value!)));
      }
    }

    if (await _budget.consume('volume')) {
      final volume = await _get('/api/computer/volume');
      if (volume.isOk) {
        _updateSnapshot(_snapshot.copyWith(volume: VolumeInfo.fromJson(volume.value!)));
      }
    }

    if (await _budget.consume('apps')) {
      final apps = await _get('/api/computer/apps');
      if (apps.isOk) {
        _updateSnapshot(_snapshot.copyWith(apps: AppsInfo.fromJson(apps.value!)));
      }
    }

    if (await _budget.consume('pc_state')) {
      final pc = await _post('/api/pc/state', body: {
        'agent_id': settings.agentId,
        'pc_state': <String, dynamic>{},
      });
      if (pc.isOk) {
        _updateSnapshot(_snapshot.copyWith(pcState: PcStateResponse.fromJson(pc.value!)));
      }
    }

  }

  // --- Computer control ----------------------------------------------------

  Future<List<AppsInfo>> listApps() async {
    final r = await _get('/api/computer/apps');
    if (r.isOk) {
      final apps = AppsInfo.fromJson(r.value!);
      _updateSnapshot(_snapshot.copyWith(apps: apps));
      return [apps];
    }
    final fallback = await _get('/api/system/apps');
    if (fallback.isOk) return [AppsInfo.fromJson(fallback.value!)];
    return const [];
  }

  Future<CommandOutcome> systemControl() =>
      _runOrQueue(TaskType.systemControl, 'GET', '/api/computer/control', 'Control enviado');

  Future<CommandOutcome> lockScreen() =>
      _runOrQueue(TaskType.lock, 'GET', '/api/computer/lock', 'Bloqueo solicitado');

  Future<CommandOutcome> screenshot() =>
      _runOrQueue(TaskType.screenshot, 'GET', '/api/computer/screenshot', 'Captura solicitada');

  Future<CommandOutcome> openTarget(String target) =>
      _runOrQueue(TaskType.open, 'POST', '/api/computer/open', 'Abriendo $target',
          body: {'target': target});

  Future<CommandOutcome> execute(String command) => _runOrQueue(
        TaskType.generic,
        'POST',
        '/api/computer/execute',
        'Ejecutando comando',
        body: {'command': command},
      );

  Future<CommandOutcome> chat(String message, {String? sessionId}) => _runOrQueue(
        TaskType.chat,
        'POST',
        '/api/chat',
        'Enviando a ARIA',
        body: {'message': message, if (sessionId != null) 'session_id': sessionId},
      );

  Future<VolumeInfo?> readVolume() async {
    final r = await _get('/api/computer/volume');
    if (!r.isOk) return null;
    final v = VolumeInfo.fromJson(r.value!);
    _updateSnapshot(_snapshot.copyWith(volume: v));
    return v;
  }

  /// Sends immediately when the backend is reachable, otherwise persists to
  /// the offline queue. The caller always gets a [CommandOutcome] — this never
  /// throws (spec §5.2).
  Future<CommandOutcome> _runOrQueue(
    TaskType kind,
    String method,
    String path,
    String successMessage, {
    Map<String, dynamic>? body,
  }) async {
    final idempotencyKey = DateTime.now().microsecondsSinceEpoch.toString();

    final BackendResult<Map<String, dynamic>> result;
    if (method == 'GET') {
      result = await _get(path);
    } else {
      result = await _post(path, body: body, idempotencyKey: idempotencyKey);
    }

    if (result.isOk && !result.bodyReportedError) {
      return CommandOutcome.sent(successMessage, result.value);
    }

    if (result.error == 'backend_offline' || result.error == 'connection timed out') {
      final cmd = await queue.enqueue(kind: kind, path: path, method: method, body: body);
      _log('info', 'queued offline: ${kind.wire} ${cmd.id}');
      return CommandOutcome.queuedOffline('Sin conexión — en cola (${queue.pendingCount})');
    }

    // Server is up but refused: do not queue, surface the error.
    return CommandOutcome.failed(result.error ?? 'Error del backend');
  }

  // --- Offline replay -----------------------------------------------------

  /// Serial FIFO replay of the pending queue (spec §5.3).
  ///
  /// Never parallel: the daemon queue is order-sensitive, and a half-delivered
  /// `lock`/`open` sequence is worse than a late one.
  Future<void> replayQueue() async {
    await queue.purgeExpired();
    for (final cmd in queue.pending) {
      if (cmd.isExpired) {
        await queue.markFailed(cmd.id, 'expirado (>24h)');
        continue;
      }
      await queue.markInflight(cmd.id);

      final BackendResult<Map<String, dynamic>> result;
      if (cmd.method == 'GET') {
        result = await _get(cmd.path);
      } else {
        result = await _post(cmd.path,
            body: cmd.body, idempotencyKey: cmd.idempotencyKey);
      }

      if (result.isOk && !result.bodyReportedError) {
        await queue.remove(cmd.id);
        _log('info', 'replayed ${cmd.kind.wire} ok');
        continue;
      }

      if (result.httpStatus == 429) {
        await queue.requeue(cmd.id);
        final wait = result.retryAfterSeconds ?? 30;
        _log('warn', 'rate limited; pausing replay ${wait}s');
        unawaited(Future<void>.delayed(Duration(seconds: wait), replayQueue));
        return;
      }

      if (result.httpStatus == 401) {
        await queue.requeue(cmd.id);
        _log('warn', 'unauthorized during replay; needs re-auth');
        return;
      }

      if (result.error == 'backend_offline') {
        await queue.requeue(cmd.id);
        _scheduleReconnect();
        return;
      }

      // Idempotency-unsafe kinds (screenshot, execute) fail hard after one
      // attempt so the user decides, per spec §5.4.
      final unsafe = cmd.kind == TaskType.screenshot || cmd.path.endsWith('/execute');
      final maxAttempts = unsafe ? 1 : 5;
      if (cmd.attempts >= maxAttempts) {
        await queue.markFailed(cmd.id, result.error ?? 'falló tras $maxAttempts intentos');
        return; // do not replay past a hard failure
      }
      await queue.requeue(cmd.id);
      _log('warn', 'replay failed (${cmd.attempts}/$maxAttempts): ${result.error}');
      return;
    }
    notifyListeners();
  }

  // --- Daemon protocol ----------------------------------------------------

  /// Registers/keeps the phone alive in `SharedState.daemon_agents`
  /// (daemon.rs:252-279). Never queued: a stale heartbeat is worse than none.
  Future<bool> sendHeartbeat({String status = 'alive'}) async {
    final r = await _post('/api/daemon/heartbeat', body: {
      'agent_id': settings.agentId,
      'status': status,
    });
    return r.isOk;
  }

  /// Claims work via POST `get_pending` (daemon.rs:148-188).
  ///
  /// GET /api/daemon/task reports pending work but never assigns it, so a
  /// client using GET would loop on the same task forever (spec §4.4).
  Future<TaskResponse> claimTask() async {
    final r = await _post('/api/daemon/task', body: {
      'agent_id': settings.agentId,
      'action': 'get_pending',
    });
    if (!r.isOk) return TaskResponse.empty;
    return TaskResponse.fromJson(r.value!);
  }

  Future<TaskResponse> reportStatus(String status) async {
    final r = await _post('/api/daemon/task', body: {
      'agent_id': settings.agentId,
      'action': 'report_status',
      'status': status,
    });
    if (!r.isOk) return TaskResponse.empty;
    return TaskResponse.fromJson(r.value!);
  }

  Future<bool> reportResult({
    required String taskId,
    required String status,
    Map<String, dynamic> output = const {},
  }) async {
    final r = await _post('/api/daemon/result', body: {
      'agent_id': settings.agentId,
      'result': {
        'task_id': taskId,
        'status': status,
        'output': output,
        'executed_at': DateTime.now().toUtc().toIso8601String(),
      },
    });
    return r.isOk;
  }

  /// Polling fallback for `task_available` until the backend broadcasts it (spec §4.4).
  Future<TaskResponse> pollPendingTasks() async {
    final r = await _get('/api/daemon/task');
    if (!r.isOk) return TaskResponse.empty;
    return TaskResponse.fromJson(r.value!);
  }

  // --- Auth ---------------------------------------------------------------

  Future<BackendResult<String>> login(String username) async {
    final r = await _post('/api/auth/login', body: {'username': username});
    if (!r.isOk) return BackendResult.err(r.error ?? 'login failed');
    final token = r.value!['token']?.toString() ?? '';
    if (token.isEmpty) return BackendResult.err('no token returned');
    await settings.setUsername(username);
    await settings.setAuthToken(token);
    return BackendResult.ok(token);
  }

  // --- Rate limiting ------------------------------------------------------

  /// Local token bucket. The server has no limits yet; this keeps the client
  /// from becoming the reason one gets added (spec §4.7).
  final _budget = _RateBudget({
    'poll': _RateBudgetRule(maxTokens: 3, refillPerSecond: 1 / 5),
    'host': _RateBudgetRule(maxTokens: 2, refillPerSecond: 1 / 300),
    'volume': _RateBudgetRule(maxTokens: 2, refillPerSecond: 1 / 10),
    'apps': _RateBudgetRule(maxTokens: 2, refillPerSecond: 1 / 15),
    'pc_state': _RateBudgetRule(maxTokens: 2, refillPerSecond: 1 / 30),
    'command': _RateBudgetRule(maxTokens: 5, refillPerSecond: 1 / 2),
    'execute': _RateBudgetRule(maxTokens: 1, refillPerSecond: 1 / 30),
  });
}

class _RateBudgetRule {
  const _RateBudgetRule({required this.maxTokens, required this.refillPerSecond});

  final int maxTokens;
  final double refillPerSecond;
}

class _RateBudget {
  _RateBudget(this._rules);

  final Map<String, _RateBudgetRule> _rules;
  final Map<String, double> _tokens = {};
  final Map<String, DateTime> _updated = {};

  /// Returns true when the call is allowed.
  bool consume(String key) {
    final rule = _rules[key];
    if (rule == null) return true;
    final now = DateTime.now();
    final tokens = _tokens[key] ?? rule.maxTokens.toDouble();
    final elapsed = _updated[key] == null
        ? 0.0
        : now.difference(_updated[key]!).inMicroseconds / 1e6;
    final refilled = (tokens + elapsed * rule.refillPerSecond).clamp(0.0, rule.maxTokens.toDouble());
    if (refilled < 1) {
      _tokens[key] = refilled;
      _updated[key] = now;
      return false;
    }
    _tokens[key] = refilled - 1;
    _updated[key] = now;
    return true;
  }
}
