import 'package:flutter/material.dart';

import '../main.dart';
import '../models/pc_state.dart';
import '../models/task.dart';
import '../services/backend_service.dart';
import '../services/offline_queue.dart';
import 'dashboard.dart' show ConnectionBadge;

/// Send commands to the daemon: system_control, apps, screenshot, volume,
/// lock, plus the offline queue inspector.
/// Spec: v6/MOBILE_SYNC_SPEC.md §4.2, §5.
class CommandScreen extends StatelessWidget {
  const CommandScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final backend = AppScope.of(context);
    final queue = AppScope.of(context).queue;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Comandos'),
        actions: [
          ListenableBuilder(
            listenable: backend,
            builder: (context, _) => ConnectionBadge(
              state: backend.state,
              error: backend.lastError,
            ),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: ListenableBuilder(
        listenable: backend,
        builder: (context, _) => ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            if (!backend.isConnected) const _OfflineBanner(),
            _CommandTile(
              icon: Icons.tune,
              title: 'Control del sistema',
              subtitle: 'GET /api/computer/control',
              onTap: () => _run(context, () => backend.systemControl()),
            ),
            _CommandTile(
              icon: Icons.apps,
              title: 'Listar aplicaciones',
              subtitle: 'GET /api/computer/apps',
              onTap: () => _run(context, () => backend.listApps().then(
                    (apps) => CommandOutcome.sent(
                      apps.isEmpty ? 'Sin aplicaciones' : apps.first.running.join(', '),
                      apps.isEmpty ? null : apps.first.toJson(),
                    ),
                  )),
            ),
            _CommandTile(
              icon: Icons.photo_camera,
              title: 'Captura de pantalla',
              subtitle: 'GET /api/computer/screenshot',
              // The endpoint returns a status stub, no image payload yet (§0.2).
              onTap: () => _run(context, () => backend.screenshot()),
            ),
            _VolumeTile(backend: backend),
            _CommandTile(
              icon: Icons.lock_outline,
              title: 'Bloquear PC',
              subtitle: 'GET /api/computer/lock',
              danger: true,
              onTap: () => _run(
                context,
                () => backend.lockScreen(),
                confirm: '¿Bloquear el PC ahora?',
              ),
            ),
            _OpenTile(backend: backend),
            _ExecuteTile(backend: backend),
            const Divider(height: 24),
            _QueueSection(queue: queue, backend: backend),
            const Divider(height: 24),
            _DaemonSection(backend: backend),
          ],
        ),
      ),
    );
  }

  static Future<void> _run(
    BuildContext context,
    Future<CommandOutcome> Function() action, {
    String? confirm,
  }) async {
    if (confirm != null) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Confirmar'),
          content: Text(confirm),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Confirmar')),
          ],
        ),
      );
      if (ok != true) return;
    }

    final outcome = await action();
    if (!context.mounted) return;
    final scheme = Theme.of(context).colorScheme;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        backgroundColor: outcome.ok
            ? (outcome.queued ? Colors.orange.shade700 : scheme.inverseSurface)
            : scheme.error,
        content: Row(
          children: [
            Icon(
              outcome.ok ? (outcome.queued ? Icons.schedule : Icons.check_circle) : Icons.error,
              color: Colors.white,
              size: 18,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                outcome.message,
                style: const TextStyle(color: Colors.white, fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: Colors.orange.shade900,
      padding: const EdgeInsets.all(10),
      child: const Row(
        children: [
          Icon(Icons.cloud_off, size: 16, color: Colors.white),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Sin conexión — los comandos se guardan y se reenvían al reconectar',
              style: TextStyle(fontSize: 12, color: Colors.white),
            ),
          ),
        ],
      ),
    );
  }
}

class _CommandTile extends StatelessWidget {
  const _CommandTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.danger = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: danger ? Colors.redAccent : null),
      title: Text(title, style: TextStyle(color: danger ? Colors.redAccent : null)),
      subtitle: Text(subtitle, style: const TextStyle(fontSize: 11)),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}

class _VolumeTile extends StatefulWidget {
  const _VolumeTile({required this.backend});

  final BackendService backend;

  @override
  State<_VolumeTile> createState() => _VolumeTileState();
}

class _VolumeTileState extends State<_VolumeTile> {
  VolumeInfo? _info;
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final info = await widget.backend.readVolume();
    if (!mounted) return;
    setState(() {
      _info = info;
      _loaded = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    // The backend exposes volume as read-only; the control is informational
    // until a setter exists (spec §4.2).
    final value = _info?.volume ?? 75;
    return ListTile(
      leading: const Icon(Icons.graphic_eq),
      title: Text(_loaded ? 'Volumen: $value' : 'Volumen'),
      subtitle: const Text('GET /api/computer/volume', style: TextStyle(fontSize: 11)),
      trailing: SizedBox(
        width: 130,
        child: Slider(
          value: value.toDouble().clamp(0, 100),
          max: 100,
          label: '$value',
          onChanged: (_) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                behavior: SnackBarBehavior.floating,
                content: Text('El backend aún no expone un setter de volumen'),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _OpenTile extends StatelessWidget {
  const _OpenTile({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.open_in_new),
      title: const Text('Abrir objetivo'),
      subtitle: const Text('POST /api/computer/open', style: TextStyle(fontSize: 11)),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        final controller = TextEditingController();
        final target = await showDialog<String>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Abrir objetivo'),
            content: TextField(
              controller: controller,
              autofocus: true,
              decoration: const InputDecoration(
                hintText: 'notepad.exe, https://…, .\\scripts\\run.ps1',
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, controller.text.trim()),
                child: const Text('Abrir'),
              ),
            ],
          ),
        );
        if (target == null || target.isEmpty) return;
        if (!context.mounted) return;
        await CommandScreen._run(context, () => backend.openTarget(target));
      },
    );
  }
}

class _ExecuteTile extends StatelessWidget {
  const _ExecuteTile({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.terminal, color: Colors.redAccent),
      title: const Text('Ejecutar comando',
          style: TextStyle(color: Colors.redAccent)),
      subtitle: const Text('POST /api/computer/execute — 1 cada 30 s',
          style: TextStyle(fontSize: 11)),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        final controller = TextEditingController();
        final command = await showDialog<String>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Ejecutar comando'),
            content: TextField(
              controller: controller,
              autofocus: true,
              decoration: const InputDecoration(hintText: 'comando de shell'),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, controller.text.trim()),
                child: const Text('Ejecutar'),
              ),
            ],
          ),
        );
        if (command == null || command.isEmpty) return;
        if (!context.mounted) return;
        await CommandScreen._run(
          context,
          () => backend.execute(command),
          confirm: 'Se ejecutará en el PC:\n\n$command\n\n¿Continuar?',
        );
      },
    );
  }
}

class _QueueSection extends StatelessWidget {
  const _QueueSection({required this.queue, required this.backend});

  final OfflineQueue queue;
  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    final items = queue.all;
    return ExpansionTile(
      leading: Badge(
        isLabelVisible: queue.pendingCount > 0,
        label: Text('${queue.pendingCount}'),
        child: const Icon(Icons.outbox),
      ),
      title: const Text('Cola offline'),
      subtitle: Text('${queue.pendingCount} pendientes · ${queue.failedCount} fallidos',
          style: const TextStyle(fontSize: 11)),
      trailing: IconButton(
        icon: const Icon(Icons.refresh, size: 18),
        tooltip: 'Reintentar ahora',
        onPressed: () => backend.replayQueue(),
      ),
      children: [
        if (items.isEmpty)
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('Cola vacía', style: TextStyle(fontSize: 12, color: Colors.white38)),
          ),
        for (final cmd in items)
          ListTile(
            dense: true,
            leading: Icon(
              switch (cmd.state) {
                QueuedCommandState.failed => Icons.error_outline,
                QueuedCommandState.inflight => Icons.sync,
                QueuedCommandState.done => Icons.check,
                QueuedCommandState.pending => Icons.schedule,
              },
              size: 16,
              color: cmd.state == QueuedCommandState.failed ? Colors.redAccent : null,
            ),
            title: Text('${cmd.kind.label} · ${cmd.method} ${cmd.path}',
                style: const TextStyle(fontSize: 12)),
            subtitle: Text(
              [
                _ago(cmd.createdAtDate),
                'intentos ${cmd.attempts}',
                if (cmd.lastError != null) cmd.lastError!,
              ].join(' · '),
              style: const TextStyle(fontSize: 10, color: Colors.white38),
            ),
            trailing: cmd.state == QueuedCommandState.failed
                ? TextButton(
                    onPressed: () => queue.requeue(cmd.id),
                    child: const Text('Reintentar'),
                  )
                : IconButton(
                    icon: const Icon(Icons.delete_outline, size: 18),
                    onPressed: () => queue.remove(cmd.id),
                  ),
          ),
        if (queue.failedCount > 0)
          Padding(
            padding: const EdgeInsets.all(8),
            child: OutlinedButton.icon(
              onPressed: () async {
                await queue.retryAllFailed();
                await backend.replayQueue();
              },
              icon: const Icon(Icons.restore, size: 16),
              label: const Text('Reintentar todos los fallidos'),
            ),
          ),
      ],
    );
  }

  static String _ago(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inSeconds < 60) return 'hace ${d.inSeconds}s';
    if (d.inMinutes < 60) return 'hace ${d.inMinutes}m';
    return 'hace ${d.inHours}h';
  }
}

class _DaemonSection extends StatelessWidget {
  const _DaemonSection({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      leading: const Icon(Icons.hub),
      title: const Text('Nodo daemon'),
      subtitle: Text(backend.settings.agentId, style: const TextStyle(fontSize: 11)),
      children: [
        ListTile(
          leading: const Icon(Icons.favorite, size: 18),
          title: const Text('Enviar heartbeat'),
          subtitle: const Text('POST /api/daemon/heartbeat', style: TextStyle(fontSize: 10)),
          onTap: () async {
            final ok = await backend.sendHeartbeat();
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              behavior: SnackBarBehavior.floating,
              content: Text(ok
                  ? 'Heartbeat enviado — el teléfono aparece en /api/agents/status'
                  : 'Heartbeat falló'),
            ));
          },
        ),
        ListTile(
          leading: const Icon(Icons.assignment_ind, size: 18),
          title: const Text('Reclamar tarea'),
          subtitle: const Text(
            'POST /api/daemon/task (action=get_pending) — no usa GET, que nunca asigna',
            style: TextStyle(fontSize: 10),
          ),
          onTap: () async {
            final res = await backend.claimTask();
            if (!context.mounted) return;
            await backend.reportResult(
              taskId: res.task?.id ?? 'none',
              status: res.assigned ? 'ok' : 'skipped',
            );
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              behavior: SnackBarBehavior.floating,
              content: Text(res.assigned
                  ? 'Tarea ${res.task!.id} (${res.task!.taskType.label}) reclamada'
                  : 'Sin tareas (${res.status})'),
            ));
          },
        ),
      ],
    );
  }
}
