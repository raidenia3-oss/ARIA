import 'package:flutter/material.dart';

import '../main.dart';
import '../models/pc_state.dart';
import '../services/backend_service.dart';

/// Real-time PC status: CPU, memory, uptime, active agents.
/// Spec: v6/MOBILE_SYNC_SPEC.md §3.3, §4.1.
class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final backend = AppScope.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('ARIA — Estado'),
        actions: [
          ListenableBuilder(
            listenable: backend,
            builder: (context, _) => Padding(
              padding: const EdgeInsets.only(right: 12),
              child: ConnectionBadge(state: backend.state, error: backend.lastError),
            ),
          ),
        ],
      ),
      body: ListenableBuilder(
        listenable: backend,
        builder: (context, _) {
          final s = backend.snapshot;
          if (s.isEmpty && !backend.isConnected) {
            return const _EmptyState();
          }
          return RefreshIndicator(
            onRefresh: backend.refreshAll,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                _HostCard(snapshot: s),
                _MetricGrid(snapshot: s),
                _AgentsCard(snapshot: s),
                if (s.pcState != null) _PcStateCard(state: s.pcState!),
                if (s.apps != null && s.apps!.running.isNotEmpty) _AppsCard(apps: s.apps!),
                _SyncFooter(backend: backend),
                if (backend.pendingAlerts.isNotEmpty) _AlertsCard(backend: backend),
              ],
            ),
          );
        },
      ),
      floatingActionButton: ListenableBuilder(
        listenable: backend,
        builder: (context, _) => FloatingActionButton.small(
          onPressed: backend.isConnected ? null : backend.connect,
          tooltip: backend.isConnected ? 'Conectado' : 'Reconectar',
          child: Icon(backend.isConnected ? Icons.wifi : Icons.wifi_off),
        ),
      ),
      backgroundColor: theme.scaffoldBackgroundColor,
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, size: 48),
            const SizedBox(height: 16),
            const Text('Sin datos del backend',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            const Text(
              'Configura la URL en Ajustes. Por defecto: http://127.0.0.1:8002',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class ConnectionBadge extends StatelessWidget {
  const ConnectionBadge({super.key, required this.state, required this.error});

  final ConnectionState state;
  final String error;

  @override
  Widget build(BuildContext context) {
    final (label, color) = switch (state) {
      ConnectionState.connected => ('En línea', Colors.greenAccent),
      ConnectionState.connecting => ('Conectando', Colors.amberAccent),
      ConnectionState.degraded => ('Degradado', Colors.orangeAccent),
      ConnectionState.backoff => ('Reintentando', Colors.amberAccent),
      ConnectionState.disconnected => ('Sin conexión', Colors.redAccent),
    };
    return Tooltip(
      message: error.isEmpty ? label : '$label — $error',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle, size: 10, color: color),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(fontSize: 12, color: color)),
        ],
      ),
    );
  }
}

class _HostCard extends StatelessWidget {
  const _HostCard({required this.snapshot});

  final PcStateSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final host = snapshot.host;
    final status = snapshot.status;
    return Card(
      child: ListTile(
        leading: const Icon(Icons.computer),
        title: Text(host?.hostname ?? 'PC desconocido'),
        subtitle: Text(
          [
            host?.os ?? '',
            host?.arch ?? '',
            status?.framework ?? '',
            if (status != null) status.version,
          ].where((e) => e.isNotEmpty).join(' · '),
        ),
        trailing: status == null
            ? null
            : Text(status.mode, style: const TextStyle(fontSize: 11)),
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.snapshot});

  final PcStateSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final cpu = snapshot.cpu ?? CpuInfo.unavailable;
    final memory = snapshot.memory;
    final status = snapshot.status;
    final volume = snapshot.volume;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        childAspectRatio: 1.7,
        children: [
          _MetricTile(
            icon: Icons.memory,
            label: 'CPU',
            // The backend has no CPU endpoint; /api/computer/status returns the
            // architecture string, not a load value. Spec §0.2.2.
            value: cpu.available ? '${cpu.usagePercent.toStringAsFixed(0)}%' : '—',
            progress: cpu.available ? cpu.usagePercent / 100 : null,
            hint: cpu.available ? null : 'sin endpoint /api/system/cpu',
          ),
          _MetricTile(
            icon: Icons.developer_board,
            label: 'Memoria',
            value: memory == null ? '—' : '${memory.usagePercent.toStringAsFixed(0)}%',
            progress: memory == null ? null : memory.usagePercent / 100,
            hint: memory == null ? null : '${memory.usedLabel} / ${memory.totalLabel}',
          ),
          _MetricTile(
            icon: Icons.timer_outlined,
            label: 'Uptime',
            value: status?.uptimeLabel ?? '—',
            hint: status == null
                ? null
                : '${status.requestsServed} req · ${status.chatsProcessed} chats',
          ),
          _MetricTile(
            icon: Icons.graphic_eq,
            label: 'Volumen',
            value: volume == null ? '—' : '${volume.volume}',
            hint: volume == null ? null : (volume.muted ? 'silenciado' : 'activo'),
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.icon,
    required this.label,
    required this.value,
    this.progress,
    this.hint,
  });

  final IconData icon;
  final String label;
  final String value;
  final double? progress;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Icon(icon, size: 16, color: scheme.primary),
                const SizedBox(width: 6),
                Text(label, style: const TextStyle(fontSize: 12)),
              ],
            ),
            Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
            if (progress != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(value: progress!.clamp(0.0, 1.0), minHeight: 4),
              ),
            if (hint != null)
              Text(hint!, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 10, color: Colors.white54)),
          ],
        ),
      ),
    );
  }
}

class _AgentsCard extends StatelessWidget {
  const _AgentsCard({required this.snapshot});

  final PcStateSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final agents = snapshot.agents;
    final status = snapshot.status;
    final daemonAgents = status?.daemonAgents ?? 0;
    final pending = status?.pendingTasks ?? 0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Agentes', style: Theme.of(context).textTheme.titleMedium),
                Text('$daemonAgents daemon · $pending pendientes',
                    style: const TextStyle(fontSize: 11, color: Colors.white54)),
              ],
            ),
            const SizedBox(height: 8),
            if (agents == null || agents.agents.isEmpty)
              const Text('Sin datos de agentes', style: TextStyle(color: Colors.white38))
            else
              ...agents.agents.map((a) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      children: [
                        Icon(
                          a.isBusy ? Icons.play_circle : Icons.circle,
                          size: 12,
                          color: a.isBusy ? Colors.amberAccent : Colors.greenAccent,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(a.name,
                              style: const TextStyle(fontSize: 13),
                              overflow: TextOverflow.ellipsis),
                        ),
                        Text(a.role, style: const TextStyle(fontSize: 10, color: Colors.white38)),
                      ],
                    ),
                  )),
          ],
        ),
      ),
    );
  }
}

class _PcStateCard extends StatelessWidget {
  const _PcStateCard({required this.state});

  final PcStateResponse state;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(state.active ? Icons.bolt : Icons.bolt_outlined),
        title: Text(state.active ? 'PC activo' : 'PC inactivo'),
        subtitle: Text(
          // The backend returns a hardcoded stub (daemon.rs:109-121); saying so
          // beats presenting fiction as telemetry. Spec §3.6.
          state.isStubbed
              ? 'El estado del PC aún no es real en este backend (stub)'
              : 'Inactivo ${state.idleSeconds}s · ${state.sessionUser}',
          style: TextStyle(
            fontSize: 12,
            color: state.isStubbed ? Colors.orangeAccent : Colors.white54,
          ),
        ),
      ),
    );
  }
}

class _AppsCard extends StatelessWidget {
  const _AppsCard({required this.apps});

  final AppsInfo apps;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.apps),
        title: Text('Procesos (${apps.running.length})'),
        children: [
          for (final app in apps.running)
            ListTile(
              dense: true,
              title: Text(app, style: const TextStyle(fontSize: 13)),
            ),
        ],
      ),
    );
  }
}

class _AlertsCard extends StatelessWidget {
  const _AlertsCard({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.orange.withOpacity(0.12),
      child: ExpansionTile(
        leading: const Icon(Icons.warning_amber, color: Colors.orangeAccent),
        title: Text('Alertas (${backend.pendingAlerts.length})'),
        children: [
          for (final alert in backend.pendingAlerts.reversed)
            ListTile(
              dense: true,
              title: Text(alert, style: const TextStyle(fontSize: 12)),
            ),
        ],
      ),
    );
  }
}

class _SyncFooter extends StatelessWidget {
  const _SyncFooter({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    final s = backend.snapshot;
    final status = s.status;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            backend.lastSyncAt == null
                ? 'Sin sincronizar'
                : 'Sincronizado ${_ago(backend.lastSyncAt!)}',
            style: const TextStyle(fontSize: 11, color: Colors.white38),
          ),
          Text(
            status == null ? '' : 'puerto ${status.port}',
            style: const TextStyle(fontSize: 11, color: Colors.white38),
          ),
        ],
      ),
    );
  }

  static String _ago(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inSeconds < 60) return 'hace ${d.inSeconds}s';
    if (d.inMinutes < 60) return 'hace ${d.inMinutes}m';
    return 'hace ${d.inHours}h';
  }
}
