/// Dart mirrors of the daemon task protocol.
/// Source: v6/axum-poc/src/daemon.rs (`struct Task`, `struct TaskResult`,
/// `struct TaskResponse`) and state.rs (`SharedState.task_queue`).

/// Task kinds the mobile client understands. Anything unrecognised decodes as
/// [TaskType.generic] rather than throwing — the backend's `task_type` is
/// free-form (daemon.rs:173 defaults to "generic").
enum TaskType {
  systemControl('system_control'),
  apps('apps'),
  screenshot('screenshot'),
  volume('volume'),
  lock('lock'),
  open('open'),
  chat('chat'),
  generic('generic');

  const TaskType(this.wire);

  final String wire;

  static TaskType fromWire(String? value) {
    for (final t in TaskType.values) {
      if (t.wire == value) return t;
    }
    return TaskType.generic;
  }

  String get label => switch (this) {
        TaskType.systemControl => 'System control',
        TaskType.apps => 'List apps',
        TaskType.screenshot => 'Screenshot',
        TaskType.volume => 'Volume',
        TaskType.lock => 'Lock PC',
        TaskType.open => 'Open target',
        TaskType.chat => 'Chat',
        TaskType.generic => 'Generic',
      };
}

/// `struct Task` (daemon.rs:22-30).
class Task {
  const Task({
    required this.id,
    required this.taskType,
    required this.payload,
    required this.assignedTo,
    required this.status,
    required this.createdAt,
  });

  final String id;
  final TaskType taskType;
  final Map<String, dynamic> payload;
  final String? assignedTo;
  final String status;
  final int createdAt;

  bool get isPending => status == 'pending';
  bool get isAssigned => status == 'assigned';

  DateTime? get createdAtDate =>
      createdAt == 0 ? null : DateTime.fromMillisecondsSinceEpoch(createdAt * 1000);

  factory Task.fromJson(Map<String, dynamic> json) {
    final rawPayload = json['payload'];
    return Task(
      id: json['id']?.toString() ?? 'unknown',
      taskType: TaskType.fromWire(json['task_type']?.toString()),
      payload: rawPayload is Map
          ? rawPayload.map((k, v) => MapEntry(k.toString(), v))
          : <String, dynamic>{},
      assignedTo: json['assigned_to']?.toString(),
      status: json['status']?.toString() ?? 'pending',
      createdAt: _int(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'task_type': taskType.wire,
        'payload': payload,
        'assigned_to': assignedTo,
        'status': status,
        'created_at': createdAt,
      };

  @override
  String toString() => 'Task($id, ${taskType.wire}, $status)';
}

/// `struct TaskResult` (daemon.rs:32-39). `executed_at` is an ISO-8601 string,
/// not an epoch — parse failures degrade to null.
class TaskResult {
  const TaskResult({
    required this.taskId,
    required this.agentId,
    required this.status,
    required this.output,
    required this.executedAt,
  });

  final String taskId;
  final String agentId;
  final String status;
  final Map<String, dynamic> output;
  final String executedAt;

  DateTime? get executedAtDate => DateTime.tryParse(executedAt);

  bool get succeeded => status == 'ok' || status == 'success' || status == 'completed';

  factory TaskResult.fromJson(Map<String, dynamic> json) {
    final rawOutput = json['output'];
    return TaskResult(
      taskId: json['task_id']?.toString() ?? 'unknown',
      agentId: json['agent_id']?.toString() ?? 'unknown',
      status: json['status']?.toString() ?? 'unknown',
      output: rawOutput is Map
          ? rawOutput.map((k, v) => MapEntry(k.toString(), v))
          : <String, dynamic>{},
      executedAt: json['executed_at']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'task_id': taskId,
        'agent_id': agentId,
        'status': status,
        'output': output,
        'executed_at': executedAt,
      };
}

/// `struct TaskResponse` (daemon.rs:59-64) — the reply to
/// `POST /api/daemon/task` and `GET /api/daemon/task`.
class TaskResponse {
  const TaskResponse({
    required this.available,
    required this.task,
    required this.status,
  });

  final bool available;
  final Task? task;
  final String status;

  /// `get_pending` found work.
  bool get assigned => status == 'task_assigned';

  /// `get_pending` found nothing. Note the server also uses
  /// `"<n>_pending"` for a non-zero count reported by the GET variant
  /// (daemon.rs:136) — treat anything non-"no_tasks" as "work exists".
  bool get noTasks => status == 'no_tasks';

  static const TaskResponse empty =
      TaskResponse(available: false, task: null, status: 'no_tasks');

  factory TaskResponse.fromJson(Map<String, dynamic> json) {
    final rawTask = json['task'];
    return TaskResponse(
      available: json['available'] == true,
      task: rawTask is Map
          ? Task.fromJson(rawTask.map((k, v) => MapEntry(k.toString(), v)))
          : null,
      status: json['status']?.toString() ?? 'unknown',
    );
  }

  Map<String, dynamic> toJson() => {
        'available': available,
        'task': task?.toJson(),
        'status': status,
      };
}

/// An entry of `SharedState.daemon_agents` (`struct AgentInfo`, state.rs:83-89).
/// Exposed to the dashboard only indirectly, through `/api/agents/status`.
class DaemonAgent {
  const DaemonAgent({
    required this.agentId,
    required this.lastHeartbeat,
    required this.status,
    required this.currentTask,
  });

  final String agentId;
  final int lastHeartbeat;
  final String status;
  final String? currentTask;

  /// A daemon agent is considered stale after 90 s without a heartbeat
  /// (the client itself beats every 30 s — spec §4.4).
  bool get isStale {
    if (lastHeartbeat == 0) return true;
    final age = DateTime.now().millisecondsSinceEpoch ~/ 1000 - lastHeartbeat;
    return age > 90;
  }

  factory DaemonAgent.fromJson(Map<String, dynamic> json) => DaemonAgent(
        agentId: json['agent_id']?.toString() ?? 'unknown',
        lastHeartbeat: _int(json['last_heartbeat']),
        status: json['status']?.toString() ?? 'unknown',
        currentTask: json['current_task']?.toString(),
      );

  Map<String, dynamic> toJson() => {
        'agent_id': agentId,
        'last_heartbeat': lastHeartbeat,
        'status': status,
        'current_task': currentTask,
      };
}

/// Convenience bundle for the command screen: a command's outcome, whether it
/// went to the server now or is sitting in the offline queue.
class CommandOutcome {
  const CommandOutcome({
    required this.ok,
    required this.message,
    this.queued = false,
    this.response,
  });

  final bool ok;
  final String message;
  final bool queued;
  final Map<String, dynamic>? response;

  static CommandOutcome sent(String message, [Map<String, dynamic>? response]) =>
      CommandOutcome(ok: true, message: message, response: response);

  static CommandOutcome queuedOffline(String message) =>
      CommandOutcome(ok: true, message: message, queued: true);

  static CommandOutcome failed(String message) =>
      CommandOutcome(ok: false, message: message);

  @override
  String toString() => 'CommandOutcome(ok: $ok, queued: $queued, $message)';
}

int _int(dynamic v, [int fallback = 0]) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? fallback;
  return fallback;
}
