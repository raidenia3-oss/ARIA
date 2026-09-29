import 'dart:convert';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../models/message.dart';
import 'settings_service.dart';

/// Local notification rendering + FCM data-message receiver.
/// Spec: v6/MOBILE_SYNC_SPEC.md §6.
///
/// The backend does not yet send FCM; this is the client half of the contract.
class NotificationService {
  NotificationService(this.settings);

  final SettingsService settings;

  static const AndroidChannelId = 'aria_alerts';
  static const AndroidChannelName = 'ARIA alerts';
  static const AndroidChannelDescription =
      'Tareas disponibles, resultados y alertas del sistema';

  final FlutterLocalNotificationsPlugin _local = FlutterLocalNotificationsPlugin();
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;

  bool _initialized = false;
  final List<String> _recentKeys = <String>[];

  static const int dedupeWindowSeconds = 60;
  static const int maxRecentKeys = 50;

  /// Call from `main()` before `runApp`. Never throws: notifications are
  /// optional and must not block app start on a device without FCM setup.
  Future<void> init() async {
    if (_initialized) return;
    try {
      const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
      const darwinInit = DarwinInitializationSettings(
        requestAlertPermission: true,
        requestBadgePermission: false,
        requestSoundPermission: true,
      );
      await _local.initialize(
        const InitializationSettings(android: androidInit, iOS: darwinInit),
        onDidReceiveNotificationResponse: _onTap,
      );

      final android = _local.resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>();
      await android?.createNotificationChannel(const AndroidNotificationChannel(
        AndroidChannelId,
        AndroidChannelName,
        description: AndroidChannelDescription,
        importance: Importance.high,
      ));

      final settings = await _messaging.requestPermission(alert: true, badge: false, sound: true);
      _messaging.onMessage.listen(_onForegroundMessage);
      _messaging.onMessageOpenedApp.listen(_onOpenedFromBackground);
      FirebaseMessaging.onBackgroundMessage(firebaseBackgroundHandler);

      debugPrint('[notifications] permission: $settings');
      _initialized = true;
    } catch (e) {
      debugPrint('[notifications] init failed: $e');
    }
  }

  /// Shows a local notification for a WS or FCM payload, subject to the user's
  /// per-type toggles and the 60 s dedupe window (spec §6.4).
  Future<void> showPush({
    required String type,
    required String title,
    required String body,
    Map<String, dynamic> payload = const {},
    String? dedupeKey,
  }) async {
    if (!_initialized) return;
    if (!settings.wantsNotification(type)) return;

    final key = dedupeKey ?? payload['alert_code']?.toString() ?? payload['task_id']?.toString() ?? type;
    if (!_shouldShow(key)) return;

    try {
      await _local.show(
        _notificationId(key),
        title,
        body,
        NotificationDetails(
          android: AndroidNotificationDetails(
            AndroidChannelId,
            AndroidChannelName,
            channelDescription: AndroidChannelDescription,
            importance: Importance.high,
            priority: Priority.high,
            styleInformation: BigTextStyleInformation(body),
          ),
          iOS: const DarwinNotificationDetails(presentAlert: true, presentSound: true),
        ),
        payload: jsonEncode({'type': type, ...payload}),
      );
    } catch (e) {
      debugPrint('[notifications] show failed: $e');
    }
  }

  bool _shouldShow(String key) {
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final idx = _recentKeys.indexWhere((k) => k.startsWith('$key|'));
    if (idx >= 0) {
      final parts = _recentKeys[idx].split('|');
      final last = int.tryParse(parts.last) ?? 0;
      if (now - last < dedupeWindowSeconds) return false;
      _recentKeys.removeAt(idx);
    }
    _recentKeys.add('$key|$now');
    if (_recentKeys.length > maxRecentKeys) _recentKeys.removeAt(0);
    return true;
  }

  static int _notificationId(String key) => key.hashCode & 0x7fffffff;

  void _onForegroundMessage(RemoteMessage message) {
    final payload = PushPayload.fromMap(message.data);
    showPush(
      type: payload.type,
      title: payload.title,
      body: payload.body,
      payload: payload.toJson(),
      dedupeKey: payload.alertCode,
    );
  }

  void _onOpenedFromBackground(RemoteMessage message) {
    _onForegroundMessage(message);
  }

  void _onTap(NotificationResponse response) {
    final raw = response.payload;
    if (raw == null) return;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map) {
        debugPrint('[notifications] tapped: ${decoded['type']}');
      }
    } catch (_) {
      // A payload we cannot parse is not worth crashing a tap handler over.
    }
  }
}

/// FCM handler for the background isolate. Must be a top-level function.
/// Spec §6.3: only `task_available` wakes a backgrounded app.
@pragma('vm:entry-point')
Future<void> firebaseBackgroundHandler(RemoteMessage message) async {
  final type = message.data['type'] ?? 'unknown';
  if (type != 'task_available' && type != 'task_result') return;
  debugPrint('[notifications] background: $type');
}
