import 'dart:convert';

import 'pc_state.dart';
import 'task.dart';

/// WebSocket envelope for `ws://<host>:8002/ws`.
/// Spec: v6/MOBILE_SYNC_SPEC.md Â§3.
///
/// The current Axum server (state.rs:14-69) is an echo loop that only emits
/// `connected`, `echo` and `ack`. [Message.fromWire] unwraps the `echo`
/// envelope and re-dispatches the inner JSON, so the same parser handles the
/// POC build today and the typed protocol without a client change.

enum MessageType {
  connected,
  heartbeat,
  taskAvailable,
  taskResult,
  pcStateChange,
  systemAlert,
  orbPhase,
  subscribed,
  agentStatusChange,
  echo,
  ack,
  pong,
  error,
  unknown;

  static MessageType fromWire(String? value) {
    switch (value) {
      case 'connected':
        return MessageType.connected;
      case 'heartbeat':
        return MessageType.heartbeat;
      case 'task_available':
        return MessageType.taskAvailable;
      case 'task_result':
        return MessageType.taskResult;
      case 'pc_state_change':
        return MessageType.pcStateChange;
      case 'system_alert':
        return MessageType.systemAlert;
      case 'orb_phase':
        return MessageType.orbPhase;
      case 'subscribed':
        return MessageType.subscribed;
      case 'agent_status_change':
        return MessageType.agentStatusChange;
      case 'echo':
        return MessageType.echo;
      case 'ack':
        return MessageType.ack;
      case 'pong':
        return MessageType.pong;
      case 'error':
        return MessageType.error;
      default:
        return MessageType.unknown;
    }
  }
}

class SystemAlertLevel {
  static const info = 'info';
  static const warning = 'warning';
  static const critical = 'critical';

  static String fromWire(String? v) =>
      (v == info || v == warning || v == critical) ? v! : info;
}

/// A parsed server frame. [data] is the unwrapped payload; for legacy frames
/// it is null and the typed accessors fall back to the top-level map.
class Message {
  const Message({
    required this.type,
    required this.raw,
    this.ts,
    this.seq,
    this.data = const {},
  });

  final MessageType type;
  final Map<String, dynamic> raw;
  final int? ts;
  final int? seq;
  final Map<String, dynamic> data;

  DateTime? get timestamp =>
      ts == null ? null : DateTime.fromMillisecondsSinceEpoch(ts! * 1000);

  /// Payload with envelope keys stripped; the correct source for the legacy
  /// `connected` / `echo` / `ack` frames, which have no `data` object.
  Map<String, dynamic> get body {
    final b = Map<String, dynamic>.from(raw)..removeWhere((k, _) => k == 'data');
    return b;
  }

  /// A `seq` jump larger than 1 means frames were lost; the client must
  /// re-fetch full state over REST rather than assume the gap was irrelevant
  /// (spec Â§3.1).
  bool hasSequenceGap(int lastSeq) =>
      seq != null && lastSeq > 0 && seq! > lastSeq + 1;

  // --- Typed accessors -----------------------------------------------------

  List<String> get connectedAgents {
    final list = data['agents'] ?? raw['agents'];
    if (list is List) return list.map((e) => e.toString()).toList();
    return const [];
  }

  SystemStatus? get systemStatus {
    if (type != MessageType.heartbeat) return null;
    final src = data.isEmpty ? raw : data;
    if (!src.containsKey('uptime_ms') && !src.containsKey('uptimeMs')) return null;
    return SystemStatus.fromJson(src);
  }

  Task? get task {
    switch (type) {
      case MessageType.taskAvailable:
        return _map('task') != null
            ? Task.fromJson(_map('task')!)
            : Task.fromJson(data.isEmpty ? raw : data);
      default:
        return null;
    }
  }

  TaskResult? get taskResult {
    if (type != MessageType.taskResult) return null;
    final src = data.isEmpty ? raw : data;
    return TaskResult.fromJson(src);
  }

  PcStateResponse? get pcState {
    if (type != MessageType.pcStateChange) return null;
    final src = data.isEmpty ? raw : data;
    return PcStateResponse.fromJson(src);
  }

  Alert? get alert {
    if (type != MessageType.systemAlert) return null;
    final src = data.isEmpty ? raw : data;
    return Alert.fromJson(src);
  }

  String? get text {
    return (data['message'] ?? raw['message'] ?? data['title'] ?? raw['title'])?.toString();
  }

  Map<String, dynamic>? _map(String key) {
    final v = data[key] ?? raw[key];
    if (v is Map) return v.map((k, val) => MapEntry(k.toString(), val));
    return null;
  }

  // --- Parsing -------------------------------------------------------------

  /// Parses a raw text frame. Never throws: malformed frames become
  /// [MessageType.unknown] with the raw text preserved for logging.
  static Message? tryParse(String? frame) {
    if (frame == null || frame.isEmpty) return null;
    try {
      final decoded = jsonDecode(frame);
      if (decoded is! Map) return null;
      final message = Message.fromJson(decoded.map((k, v) => MapEntry(k.toString(), v)));
      // Unwrap the POC echo envelope: `{"type":"echo","original":"<json>"}`.
      if (message.type == MessageType.echo) return _unwrapEcho(message);
      return message;
    } catch (_) {
      return Message(
        type: MessageType.unknown,
        raw: {'type': 'unknown', 'body': frame},
      );
    }
  }

  static Message? _unwrapEcho(Message echo) {
    final original = echo.raw['original'];
    if (original is! String || original.isEmpty) return null;
    final inner = tryParse(original);
    if (inner == null) return null;
    // Preserve the server's own envelope metadata when the inner frame lacks it.
    return Message(
      type: inner.type,
      raw: inner.raw,
      ts: inner.ts ?? echo.ts,
      seq: inner.seq,
      data: inner.data,
    );
  }

  factory Message.fromJson(Map<String, dynamic> json) {
    final rawData = json['data'];
    return Message(
      type: MessageType.fromWire(json['type']?.toString()),
      raw: json,
      ts: json['ts'] is num ? (json['ts'] as num).toInt() : null,
      seq: json['seq'] is num ? (json['seq'] as num).toInt() : null,
      data: rawData is Map
          ? rawData.map((k, v) => MapEntry(k.toString(), v))
          : const <String, dynamic>{},
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type.name,
        if (ts != null) 'ts': ts,
        if (seq != null) 'seq': seq,
        if (data.isNotEmpty) 'data': data,
      };

  // --- Outgoing frames -----------------------------------------------------

  static String identifyFrame({
    required String deviceId,
    String client = 'airi_mobile',
    String clientVersion = '0.1.0',
    String? platform,
  }) {
    return jsonEncode({
      'type': 'identify',
      'client': client,
      'client_version': clientVersion,
      'device_id': deviceId,
      'user_agent': platform == null ? 'Flutter' : 'Flutter/$platform',
    });
  }

  static String subscribeFrame(List<String> channels) =>
      jsonEncode({'type': 'subscribe', 'channels': channels});

  static String unsubscribeFrame(List<String> channels) =>
      jsonEncode({'type': 'unsubscribe', 'channels': channels});

  static String appPingFrame() => jsonEncode({'type': 'ping'});

  static String commandFrame({
    required String commandType,
    required String idempotencyKey,
    Map<String, dynamic> params = const {},
  }) {
    return jsonEncode({
      'type': 'command',
      'command_type': commandType,
      'idempotency_key': idempotencyKey,
      'params': params,
    });
  }

  static String ackFrame(String reference) =>
      jsonEncode({'type': 'ack', 'ref': reference});

  @override
  String toString() => 'Message(${type.name}, seq: $seq)';
}

/// Payload of a `system_alert` frame (spec Â§3.7).
class Alert {
  const Alert({
    required this.level,
    required this.code,
    required this.message,
    this.metric = const {},
    this.actions = const [],
  });

  final String level;
  final String code;
  final String message;
  final Map<String, dynamic> metric;
  final List<String> actions;

  bool get isCritical => level == SystemAlertLevel.critical;

  factory Alert.fromJson(Map<String, dynamic> json) {
    final rawMetric = json['metric'];
    final rawActions = json['actions'];
    return Alert(
      level: SystemAlertLevel.fromWire(json['level']?.toString()),
      code: json['code']?.toString() ?? 'unknown',
      message: json['message']?.toString() ?? '',
      metric: rawMetric is Map
          ? rawMetric.map((k, v) => MapEntry(k.toString(), v))
          : const <String, dynamic>{},
      actions: rawActions is List
          ? rawActions.map((e) => e.toString()).toList()
          : const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'level': level,
        'code': code,
        'message': message,
        'metric': metric,
        'actions': actions,
      };
}

/// FCM data-message payload (spec Â§6.2). Parsed in the background isolate, so
/// it must be self-contained â€” no dependency on other models.
class PushPayload {
  const PushPayload({
    required this.type,
    required this.alertLevel,
    required this.alertCode,
    required this.title,
    required this.body,
    required this.ts,
    this.metrics = const {},
    this.deepLink,
    this.server = '',
  });

  final String type;
  final String alertLevel;
  final String alertCode;
  final String title;
  final String body;
  final String ts;
  final Map<String, dynamic> metrics;
  final String? deepLink;
  final String server;

  bool get isTaskWakeup => type == 'task_available';

  DateTime? get timestamp => DateTime.tryParse(ts);

  factory PushPayload.fromMap(Map<String, dynamic> data) {
    final rawMetrics = data['metrics'];
    return PushPayload(
      type: data['type']?.toString() ?? 'unknown',
      alertLevel: SystemAlertLevel.fromWire(data['alert_level']?.toString()),
      alertCode: data['alert_code']?.toString() ?? 'unknown',
      title: data['title']?.toString() ?? 'ARIA',
      body: data['body']?.toString() ?? '',
      ts: data['ts']?.toString() ?? '',
      metrics: rawMetrics is Map
          ? rawMetrics.map((k, v) => MapEntry(k.toString(), v))
          : const <String, dynamic>{},
      deepLink: data['deep_link']?.toString(),
      server: data['server']?.toString() ?? '',
    );
  }

  factory PushPayload.fromJsonString(String raw) {
    final decoded = jsonDecode(raw);
    return PushPayload.fromMap(
        (decoded is Map ? decoded : const {}).map((k, v) => MapEntry(k.toString(), v)));
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'alert_level': alertLevel,
        'alert_code': alertCode,
        'title': title,
        'body': body,
        'ts': ts,
        'metrics': metrics,
        if (deepLink != null) 'deep_link': deepLink,
        'server': server,
      };
}

/// Bounded in-memory + Hive-backed log, capped per spec Â§7 (500 entries,
/// 200-char body truncation).
class LogEntry {
  const LogEntry({required this.ts, required this.level, required this.message});

  final DateTime ts;
  final String level;
  final String message;

  static const int maxEntries = 500;
  static const int maxMessageLength = 200;

  factory LogEntry.fromJson(Map<String, dynamic> json) => LogEntry(
        ts: DateTime.fromMillisecondsSinceEpoch((json['ts'] as num?)?.toInt() ?? 0),
        level: json['level']?.toString() ?? 'info',
        message: json['message']?.toString() ?? '',
      );

  Map<String, dynamic> toJson() =>
      {'ts': ts.millisecondsSinceEpoch, 'level': level, 'message': message};
}
