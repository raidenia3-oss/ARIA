import 'dart:async';

import 'package:hive_flutter/hive_flutter.dart';
import 'package:uuid/uuid.dart';

import '../models/task.dart';

/// Offline-first command queue backed by Hive.
///
/// Spec: v6/MOBILE_SYNC_SPEC.md §5. Every mutating command is persisted here
/// *before* it is sent, so the UI can acknowledge instantly and nothing is lost
/// when the backend is unreachable.
///
/// Hand-written TypeAdapters are used instead of build_runner so the project has
/// no codegen step.
class OfflineQueue {
  OfflineQueue._(this._box);

  static const String boxName = 'airi_offline_queue';

  final Box _box;
  static final _uuid = const Uuid();

  static Future<OfflineQueue> open() async {
    await Hive.initFlutter();
    if (!Hive.isAdapterRegistered(QueuedCommandAdapter.typeIdValue)) {
      Hive.registerAdapter(QueuedCommandAdapter());
    }
    final box = await Hive.openBox(boxName);
    final queue = OfflineQueue._(box);
    await queue._recoverInflight();
    return queue;
  }

  /// A crash mid-flight must not strand a command: `inflight` resets to
  /// `pending` on startup (spec §5.2).
  Future<void> _recoverInflight() async {
    for (final key in _box.keys.toList()) {
      final cmd = _box.get(key) as QueuedCommand?;
      if (cmd != null && cmd.state == QueuedCommandState.inflight) {
        await _box.put(key, cmd.copyWith(state: QueuedCommandState.pending));
      }
    }
  }

  // --- Reads --------------------------------------------------------------

  List<QueuedCommand> get all {
    final items = _box.values.whereType<QueuedCommand>().toList();
    items.sort((a, b) => a.createdAt.compareTo(b.createdAt));
    return items;
  }

  List<QueuedCommand> get pending =>
      all.where((c) => c.state == QueuedCommandState.pending).toList();

  List<QueuedCommand> get failed =>
      all.where((c) => c.state == QueuedCommandState.failed).toList();

  int get pendingCount => pending.length;

  int get failedCount => failed.length;

  bool get isEmpty => _box.isEmpty;

  // --- Writes -------------------------------------------------------------

  /// Persists a command. Returns it with the generated id and idempotency key
  /// so the caller can display them.
  Future<QueuedCommand> enqueue({
    required TaskType kind,
    required String path,
    required String method,
    Map<String, dynamic>? body,
  }) async {
    final cmd = QueuedCommand(
      id: _uuid.v4(),
      idempotencyKey: _uuid.v4(),
      kind: kind,
      path: path,
      method: method,
      body: body,
      createdAt: DateTime.now().millisecondsSinceEpoch,
      attempts: 0,
      state: QueuedCommandState.pending,
    );
    await _box.put(cmd.id, cmd);
    return cmd;
  }

  Future<void> markInflight(String id) async {
    final cmd = _box.get(id) as QueuedCommand?;
    if (cmd == null) return;
    await _box.put(id, cmd.copyWith(
      state: QueuedCommandState.inflight,
      attempts: cmd.attempts + 1,
    ));
  }

  Future<void> markFailed(String id, String error) async {
    final cmd = _box.get(id) as QueuedCommand?;
    if (cmd == null) return;
    await _box.put(id, cmd.copyWith(
      state: QueuedCommandState.failed,
      lastError: error,
    ));
  }

  Future<void> requeue(String id) async {
    final cmd = _box.get(id) as QueuedCommand?;
    if (cmd == null) return;
    await _box.put(id, cmd.copyWith(state: QueuedCommandState.pending, lastError: null));
  }

  Future<void> remove(String id) => _box.delete(id);

  Future<void> clear() => _box.clear();

  Future<void> retryAllFailed() async {
    for (final cmd in failed) {
      await requeue(cmd.id);
    }
  }

  /// Drops entries older than the 24 h replay TTL (spec §5.3).
  Future<int> purgeExpired() async {
    final cutoff = DateTime.now()
        .subtract(const Duration(hours: 24))
        .millisecondsSinceEpoch;
    final expired = all
        .where((c) => c.createdAt < cutoff)
        .where((c) => c.state != QueuedCommandState.inflight)
        .toList();
    for (final cmd in expired) {
      await _box.delete(cmd.id);
    }
    return expired.length;
  }
}

enum QueuedCommandState { pending, inflight, done, failed }

/// Hive type id 1. Do not reuse.
class QueuedCommand {
  const QueuedCommand({
    required this.id,
    required this.idempotencyKey,
    required this.kind,
    required this.path,
    required this.method,
    required this.createdAt,
    required this.attempts,
    required this.state,
    this.body,
    this.lastError,
  });

  final String id;
  final String idempotencyKey;
  final TaskType kind;
  final String path;
  final String method;
  final Map<String, dynamic>? body;
  final int createdAt;
  final int attempts;
  final QueuedCommandState state;
  final String? lastError;

  bool get isExpired => DateTime.now().millisecondsSinceEpoch - createdAt >
      const Duration(hours: 24).inMilliseconds;

  DateTime get createdAtDate => DateTime.fromMillisecondsSinceEpoch(createdAt);

  QueuedCommand copyWith({
    QueuedCommandState? state,
    int? attempts,
    String? lastError,
    bool clearError = false,
  }) {
    return QueuedCommand(
      id: id,
      idempotencyKey: idempotencyKey,
      kind: kind,
      path: path,
      method: method,
      body: body,
      createdAt: createdAt,
      attempts: attempts ?? this.attempts,
      state: state ?? this.state,
      lastError: clearError ? null : (lastError ?? this.lastError),
    );
  }
}

class QueuedCommandAdapter extends TypeAdapter<QueuedCommand> {
  static const int typeIdValue = 1;

  @override
  int get typeId => typeIdValue;

  @override
  QueuedCommand read(BinaryReader reader) {
    final fields = reader.readMap().cast<String, dynamic>();
    return QueuedCommand(
      id: fields['id'] as String,
      idempotencyKey: fields['idempotencyKey'] as String,
      kind: TaskType.fromWire(fields['kind'] as String?),
      path: fields['path'] as String,
      method: fields['method'] as String,
      body: (fields['body'] as Map?)?.cast<String, dynamic>(),
      createdAt: (fields['createdAt'] as num).toInt(),
      attempts: (fields['attempts'] as num).toInt(),
      state: QueuedCommandState.values.firstWhere(
        (s) => s.name == fields['state'],
        orElse: () => QueuedCommandState.pending,
      ),
      lastError: fields['lastError'] as String?,
    );
  }

  @override
  void write(BinaryWriter writer, QueuedCommand obj) {
    writer.writeMap({
      'id': obj.id,
      'idempotencyKey': obj.idempotencyKey,
      'kind': obj.kind.wire,
      'path': obj.path,
      'method': obj.method,
      'body': obj.body,
      'createdAt': obj.createdAt,
      'attempts': obj.attempts,
      'state': obj.state.name,
      'lastError': obj.lastError,
    });
  }
}
