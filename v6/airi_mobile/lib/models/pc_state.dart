import 'dart:convert';

/// Dart mirrors of the JSON emitted by the ARIA Axum backend (port 8002).
///
/// Source of truth:
///   v6/axum-poc/src/core.rs        -> /health, /api/system/status
///   v6/axum-poc/src/system.rs      -> /api/system/{memory,whois,ping,time,log,scan}
///   v6/axum-poc/src/computer.rs    -> /api/computer/*
///   v6/axum-poc/src/daemon.rs      -> PCStateResponse
///   v6/axum-poc/src/agents.rs      -> SwarmStatusResponse
///
/// Every `fromJson` is defensive: the backend currently mixes hardcoded stubs with
/// real values, so fields are all optional and never throw. See MOBILE_SYNC_SPEC.md §0.3.

double _toDouble(dynamic v, [double fallback = 0]) {
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? fallback;
  return fallback;
}

int _toInt(dynamic v, [int fallback = 0]) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? fallback;
  return fallback;
}

List<String> _toStringList(dynamic v) {
  if (v is List) return v.map((e) => e.toString()).toList();
  return const [];
}

/// `GET /health` and `GET /api/system/status` (core.rs:53-67).
class SystemStatus {
  const SystemStatus({
    required this.status,
    required this.framework,
    required this.version,
    required this.uptimeMs,
    required this.port,
    required this.mode,
    required this.requestsServed,
    required this.chatsProcessed,
    required this.daemonAgents,
    required this.pendingTasks,
    required this.completedResults,
  });

  final String status;
  final String framework;
  final String version;
  final int uptimeMs;
  final int port;
  final String mode;
  final int requestsServed;
  final int chatsProcessed;
  final int daemonAgents;
  final int pendingTasks;
  final int completedResults;

  bool get healthy => status == 'ok';

  Duration get uptime => Duration(milliseconds: uptimeMs);

  /// Human readable uptime, e.g. `2d 4h 13m`.
  String get uptimeLabel {
    final d = uptime;
    final days = d.inDays;
    final hours = d.inHours % 24;
    final minutes = d.inMinutes % 60;
    if (days > 0) return '${days}d ${hours}h ${minutes}m';
    if (hours > 0) return '${hours}h ${minutes}m';
    if (d.inMinutes > 0) return '${d.inMinutes}m ${d.inSeconds % 60}s';
    return '${d.inSeconds}s';
  }

  factory SystemStatus.fromJson(Map<String, dynamic> json) {
    return SystemStatus(
      status: json['status']?.toString() ?? 'unknown',
      framework: json['framework']?.toString() ?? 'unknown',
      version: json['version']?.toString() ?? '0.0.0',
      uptimeMs: _toInt(json['uptime_ms'] ?? json['uptimeMs']),
      port: _toInt(json['port'], 8002),
      mode: json['mode']?.toString() ?? '',
      requestsServed: _toInt(json['requests_served']),
      chatsProcessed: _toInt(json['chats_processed']),
      daemonAgents: _toInt(json['daemon_agents']),
      pendingTasks: _toInt(json['pending_tasks']),
      completedResults: _toInt(json['completed_results']),
    );
  }

  Map<String, dynamic> toJson() => {
        'status': status,
        'framework': framework,
        'version': version,
        'uptime_ms': uptimeMs,
        'port': port,
        'mode': mode,
        'requests_served': requestsServed,
        'chats_processed': chatsProcessed,
        'daemon_agents': daemonAgents,
        'pending_tasks': pendingTasks,
        'completed_results': completedResults,
      };

  @override
  String toString() => 'SystemStatus($status, ${uptimeLabel}, agents:$daemonAgents)';
}

/// `GET /api/system/memory` and `GET /api/computer/memory`.
class MemoryInfo {
  const MemoryInfo({
    required this.total,
    required this.used,
    required this.available,
    required this.usagePercent,
  });

  final int total;
  final int used;
  final int available;
  final double usagePercent;

  String get totalLabel => _bytes(total);
  String get usedLabel => _bytes(used);
  String get availableLabel => _bytes(available);

  static String _bytes(int b) {
    if (b <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = 0;
    var v = b.toDouble();
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    return '${v.toStringAsFixed(v >= 10 || i == 0 ? 0 : 1)} ${units[i]}';
  }

  factory MemoryInfo.fromJson(Map<String, dynamic> json) {
    final total = _toInt(json['total']);
    final used = _toInt(json['used']);
    return MemoryInfo(
      total: total,
      used: used,
      available: _toInt(json['available'], total - used),
      usagePercent: _toDouble(
        json['usage_percent'] ?? json['usagePercent'],
        total > 0 ? (used / total) * 100 : 0,
      ),
    );
  }

  Map<String, dynamic> toJson() => {
        'total': total,
        'used': used,
        'available': available,
        'usage_percent': usagePercent,
      };
}

/// `GET /api/system/cpu` — does not exist on the backend yet.
/// Always null until MOBILE_SYNC_SPEC.md §0.2.2 is resolved.
class CpuInfo {
  const CpuInfo({
    required this.available,
    this.usagePercent = 0,
    this.perCore = const [],
    this.tempC,
  });

  final bool available;
  final double usagePercent;
  final List<double> perCore;
  final double? tempC;

  static const CpuInfo unavailable = CpuInfo(available: false);

  factory CpuInfo.fromJson(Map<String, dynamic> json) {
    final raw = json['usage_percent'] ?? json['usagePercent'];
    if (raw == null) return CpuInfo.unavailable;
    return CpuInfo(
      available: true,
      usagePercent: _toDouble(raw),
      perCore: (json['per_core'] as List?)
              ?.map((e) => _toDouble(e))
              .toList() ??
          const [],
      tempC: json['temp_c'] == null ? null : _toDouble(json['temp_c']),
    );
  }

  Map<String, dynamic> toJson() => {
        'available': available,
        'usage_percent': usagePercent,
        'per_core': perCore,
        'temp_c': tempC,
      };
}

/// `GET /api/system/whois` (system.rs:56-65).
class HostInfo {
  const HostInfo({
    required this.hostname,
    required this.os,
    required this.arch,
    required this.framework,
  });

  final String hostname;
  final String os;
  final String arch;
  final String framework;

  factory HostInfo.fromJson(Map<String, dynamic> json) {
    return HostInfo(
      hostname: json['hostname']?.toString() ?? 'unknown',
      os: json['os']?.toString() ?? 'unknown',
      arch: json['arch']?.toString() ?? 'unknown',
      framework: json['framework']?.toString() ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
        'hostname': hostname,
        'os': os,
        'arch': arch,
        'framework': framework,
      };
}

/// `GET /api/system/volume` and `GET /api/computer/volume`.
class VolumeInfo {
  const VolumeInfo({required this.volume, required this.muted});

  final int volume;
  final bool muted;

  factory VolumeInfo.fromJson(Map<String, dynamic> json) => VolumeInfo(
        volume: _toInt(json['volume'], 75),
        muted: json['muted'] == true,
      );

  Map<String, dynamic> toJson() => {'volume': volume, 'muted': muted};
}

/// `POST /api/pc/state` -> `struct PCStateResponse` (daemon.rs:51-57).
///
/// NOTE: the current handler returns hardcoded values and discards the request
/// body (daemon.rs:109-121). Treat this as a liveness signal only.
/// See MOBILE_SYNC_SPEC.md §3.6.
class PcStateResponse {
  const PcStateResponse({
    required this.active,
    required this.idleSeconds,
    required this.sessionUser,
    required this.timestamp,
    required this.isStubbed,
  });

  final bool active;
  final int idleSeconds;
  final String sessionUser;
  final int timestamp;

  /// True when the values look like the backend's hardcoded stub, so the UI can
  /// say so rather than presenting fiction as telemetry.
  final bool isStubbed;

  factory PcStateResponse.fromJson(Map<String, dynamic> json) {
    return PcStateResponse(
      active: json['active'] == true,
      idleSeconds: _toInt(json['idle_seconds']),
      sessionUser: json['session_user']?.toString() ?? 'unknown',
      timestamp: _toInt(json['timestamp']),
      isStubbed: json['session_user'] == 'ARIA-USB' && _toInt(json['idle_seconds']) == 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'active': active,
        'idle_seconds': idleSeconds,
        'session_user': sessionUser,
        'timestamp': timestamp,
      };
}

/// One entry of `GET /api/agents/status` -> `agents[]` (agents.rs:16-23).
class SwarmAgent {
  const SwarmAgent({
    required this.name,
    required this.role,
    required this.status,
    required this.taskCount,
    required this.errorCount,
  });

  final String name;
  final String role;
  final String status;
  final int taskCount;
  final int errorCount;

  bool get isBusy => status == 'busy' || status == 'working';

  factory SwarmAgent.fromJson(Map<String, dynamic> json) {
    return SwarmAgent(
      name: json['name']?.toString() ?? 'unknown',
      role: json['role']?.toString() ?? '',
      status: json['status']?.toString() ?? 'unknown',
      taskCount: _toInt(json['task_count']),
      errorCount: _toInt(json['error_count']),
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'role': role,
        'status': status,
        'task_count': taskCount,
        'error_count': errorCount,
      };
}

/// `GET /api/agents/status` -> `struct SwarmStatusResponse` (agents.rs:18-22).
class AgentsStatus {
  const AgentsStatus({
    required this.name,
    required this.agentCount,
    required this.agents,
  });

  final String name;
  final int agentCount;
  final List<SwarmAgent> agents;

  int get online =>
      agents.where((a) => a.status == 'alive' || a.status == 'busy' || a.status == 'idle').length;

  static const AgentsStatus empty = AgentsStatus(name: 'ARIA-Swarm', agentCount: 0, agents: []);

  factory AgentsStatus.fromJson(Map<String, dynamic> json) {
    final list = (json['agents'] as List?)
            ?.whereType<Map>()
            .map((e) => SwarmAgent.fromJson(e.cast<String, dynamic>()))
            .toList() ??
        const <SwarmAgent>[];
    return AgentsStatus(
      name: json['name']?.toString() ?? 'ARIA-Swarm',
      agentCount: _toInt(json['agent_count'], list.length),
      agents: list,
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'agent_count': agentCount,
        'agents': agents.map((a) => a.toJson()).toList(),
      };
}

/// `GET /api/system/apps` and `GET /api/computer/apps`.
class AppsInfo {
  const AppsInfo({required this.running});

  final List<String> running;

  static const AppsInfo empty = AppsInfo(running: []);

  factory AppsInfo.fromJson(Map<String, dynamic> json) =>
      AppsInfo(running: _toStringList(json['running'] ?? json['processes']));

  Map<String, dynamic> toJson() => {'running': running};
}

/// Aggregate rendered by `screens/dashboard.dart`.
///
/// Each field is nullable because any single poll can fail while the others
/// succeed; the dashboard keeps showing the last good value per field.
class PcStateSnapshot {
  const PcStateSnapshot({
    this.status,
    this.memory,
    this.cpu,
    this.host,
    this.agents,
    this.volume,
    this.apps,
    this.pcState,
    this.capturedAt,
  });

  final SystemStatus? status;
  final MemoryInfo? memory;
  final CpuInfo? cpu;
  final HostInfo? host;
  final AgentsStatus? agents;
  final VolumeInfo? volume;
  final AppsInfo? apps;
  final PcStateResponse? pcState;
  final DateTime? capturedAt;

  bool get isEmpty => status == null && memory == null && agents == null;

  int get agentCount => status?.daemonAgents ?? agents?.agentCount ?? 0;

  int get pendingTasks => status?.pendingTasks ?? 0;

  PcStateSnapshot copyWith({
    SystemStatus? status,
    MemoryInfo? memory,
    CpuInfo? cpu,
    HostInfo? host,
    AgentsStatus? agents,
    VolumeInfo? volume,
    AppsInfo? apps,
    PcStateResponse? pcState,
    DateTime? capturedAt,
  }) {
    return PcStateSnapshot(
      status: status ?? this.status,
      memory: memory ?? this.memory,
      cpu: cpu ?? this.cpu,
      host: host ?? this.host,
      agents: agents ?? this.agents,
      volume: volume ?? this.volume,
      apps: apps ?? this.apps,
      pcState: pcState ?? this.pcState,
      capturedAt: capturedAt ?? this.capturedAt,
    );
  }

  Map<String, dynamic> toJson() => {
        'status': status?.toJson(),
        'memory': memory?.toJson(),
        'cpu': cpu?.toJson(),
        'host': host?.toJson(),
        'agents': agents?.toJson(),
        'volume': volume?.toJson(),
        'apps': apps?.toJson(),
        'pc_state': pcState?.toJson(),
        'captured_at': capturedAt?.toIso8601String(),
      };

  factory PcStateSnapshot.fromJson(Map<String, dynamic> json) {
    return PcStateSnapshot(
      status: json['status'] == null ? null : SystemStatus.fromJson((json['status'] as Map).cast<String, dynamic>()),
      memory: json['memory'] == null ? null : MemoryInfo.fromJson((json['memory'] as Map).cast<String, dynamic>()),
      cpu: json['cpu'] == null ? null : CpuInfo.fromJson((json['cpu'] as Map).cast<String, dynamic>()),
      host: json['host'] == null ? null : HostInfo.fromJson((json['host'] as Map).cast<String, dynamic>()),
      agents: json['agents'] == null ? null : AgentsStatus.fromJson((json['agents'] as Map).cast<String, dynamic>()),
      volume: json['volume'] == null ? null : VolumeInfo.fromJson((json['volume'] as Map).cast<String, dynamic>()),
      apps: json['apps'] == null ? null : AppsInfo.fromJson((json['apps'] as Map).cast<String, dynamic>()),
      pcState: json['pc_state'] == null ? null : PcStateResponse.fromJson((json['pc_state'] as Map).cast<String, dynamic>()),
      capturedAt: DateTime.tryParse(json['captured_at']?.toString() ?? ''),
    );
  }

  String encode() => jsonEncode(toJson());
}
