import 'package:hive_flutter/hive_flutter.dart';
import 'package:uuid/uuid.dart';

/// Persisted client configuration.
///
/// Base URL is configurable: it defaults to `http://127.0.0.1:8002` (Android
/// emulator loopback alias is handled in [normalizeBaseUrl]) and is overridden
/// from the Settings screen for a real LAN host.
class SettingsService extends ChangeNotifier {
  SettingsService._(this._box);

  static const String boxName = 'airi_settings';

  static const String defaultBaseUrl = 'http://127.0.0.1:8002';
  static const int defaultPollIntervalSeconds = 5;

  final Box _box;
  static final _uuid = const Uuid();

  static Future<SettingsService> open() async {
    await Hive.initFlutter();
    final box = await Hive.openBox(boxName);
    return SettingsService._(box);
  }

  // --- Backend ------------------------------------------------------------

  String get baseUrl => (_box.get('baseUrl') as String?) ?? defaultBaseUrl;

  /// Allow plaintext only to loopback. The spec (§7) requires TLS for any
  /// non-loopback host; the user can override the warning explicitly.
  bool get allowInsecureRemote => (_box.get('allowInsecureRemote') as bool?) ?? false;

  String get deviceId {
    final existing = _box.get('deviceId') as String?;
    if (existing != null && existing.isNotEmpty) return existing;
    final generated = _uuid.v4();
    _box.put('deviceId', generated);
    return generated;
  }

  /// Identity the phone registers under in `SharedState.daemon_agents`.
  String get agentId => 'airi_mobile-${deviceId.substring(0, 8)}';

  String get authToken => (_box.get('authToken') as String?) ?? '';

  String get username => (_box.get('username') as String?) ?? '';

  // --- Sync behaviour -----------------------------------------------------

  bool get autoConnect => (_box.get('autoConnect') as bool?) ?? true;

  bool get replayOnReconnect => (_box.get('replayOnReconnect') as bool?) ?? true;

  int get pollIntervalSeconds =>
      (_box.get('pollIntervalSeconds') as int?) ?? defaultPollIntervalSeconds;

  /// Backgrounded for more than 5 minutes, or battery under 15% — the client
  /// drops the socket and polls instead (spec §1.5).
  bool get preferPollingWhenIdle => (_box.get('preferPollingWhenIdle') as bool?) ?? true;

  // --- Notification toggles (spec §6.4) -----------------------------------

  bool get notifyTaskAvailable => (_box.get('notifyTaskAvailable') as bool?) ?? true;

  bool get notifyTaskResult => (_box.get('notifyTaskResult') as bool?) ?? true;

  bool get notifySystemAlert => (_box.get('notifySystemAlert') as bool?) ?? true;

  bool get notifyPcStateChange => (_box.get('notifyPcStateChange') as bool?) ?? false;

  bool wantsNotification(String type) => switch (type) {
        'task_available' => notifyTaskAvailable,
        'task_result' => notifyTaskResult,
        'system_alert' => notifySystemAlert,
        'pc_state_change' => notifyPcStateChange,
        _ => false,
      };

  // --- WS channels (spec §2) ---------------------------------------------

  List<String> get channels => (_box.get('channels') as List?)?.cast<String>() ??
      const ['system', 'tasks', 'agents', 'alerts'];

  // --- Derived URLs -------------------------------------------------------

  String get wsUrl {
    final base = baseUrl;
    final uri = Uri.parse(base);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    final query = authToken.isEmpty ? '' : '?token=${Uri.encodeQueryComponent(authToken)}';
    return uri.replace(scheme: scheme, path: '/ws', query: query).toString();
  }

  /// `10.0.2.2` is the Android emulator's alias for the host machine, which is
  /// where Axum binds (`127.0.0.1:8002`).
  String get effectiveBaseUrl {
    if (baseUrl.contains('127.0.0.1') || baseUrl.contains('localhost')) {
      return baseUrl.replaceFirst(RegExp(r'//(127\.0\.0\.1|localhost)'), '//10.0.2.2');
    }
    return baseUrl;
  }

  /// Returns a validation error string, or null when the URL is usable.
  String? validateBaseUrl(String value) {
    final uri = Uri.tryParse(value.trim());
    if (uri == null || uri.scheme.isEmpty || uri.host.isEmpty) {
      return 'URL inválido';
    }
    if (uri.scheme != 'http' && uri.scheme != 'https') {
      return 'Solo http:// o https://';
    }
    final isLoopback = uri.host == '127.0.0.1' ||
        uri.host == 'localhost' ||
        uri.host == '10.0.2.2' ||
        uri.host == '::1';
    if (uri.scheme == 'http' && !isLoopback && !allowInsecureRemote) {
      return 'Se requiere HTTPS para hosts remotos. Actívalo en "permitir HTTP remoto".';
    }
    return null;
  }

  static String normalizeBaseUrl(String value) {
    var v = value.trim();
    if (v.isEmpty) return defaultBaseUrl;
    if (!v.startsWith('http://') && !v.startsWith('https://')) {
      v = 'http://$v';
    }
    while (v.endsWith('/')) {
      v = v.substring(0, v.length - 1);
    }
    return v;
  }

  // --- Setters ------------------------------------------------------------

  Future<void> setBaseUrl(String value) => _box.put('baseUrl', normalizeBaseUrl(value));

  Future<void> setAllowInsecureRemote(bool value) async {
    await _box.put('allowInsecureRemote', value);
    notifyListeners();
  }

  Future<void> setAuthToken(String value) => _box.put('authToken', value.trim());

  Future<void> setUsername(String value) => _box.put('username', value.trim());

  Future<void> setAutoConnect(bool value) => _box.put('autoConnect', value);

  Future<void> setReplayOnReconnect(bool value) => _box.put('replayOnReconnect', value);

  Future<void> setPollInterval(int seconds) =>
      _box.put('pollIntervalSeconds', seconds.clamp(2, 120));

  Future<void> setPreferPollingWhenIdle(bool value) =>
      _box.put('preferPollingWhenIdle', value);

  Future<void> setChannels(List<String> value) => _box.put('channels', value);

  Future<void> setNotificationToggle(String key, bool value) async {
    await _box.put(key, value);
    notifyListeners();
  }
}

/// Minimal ChangeNotifier so the app does not need the `provider` package.
abstract class ChangeNotifier {
  final List<void Function()> _listeners = [];

  void addListener(void Function() listener) => _listeners.add(listener);

  void removeListener(void Function() listener) => _listeners.remove(listener);

  void notifyListeners() {
    for (final l in List.of(_listeners)) {
      l();
    }
  }

  void dispose() {
    _listeners.clear();
  }
}
