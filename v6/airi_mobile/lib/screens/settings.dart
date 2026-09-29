import 'package:flutter/material.dart';

import '../main.dart';
import '../services/backend_service.dart';
import '../services/settings_service.dart';

/// Backend URL configuration, connection controls, notification toggles.
/// Spec: v6/MOBILE_SYNC_SPEC.md §2, §6.4, §7.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _urlController;
  late final TextEditingController _tokenController;
  late final TextEditingController _usernameController;
  bool _initialized = false;
  bool _testing = false;
  String? _urlError;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_initialized) return;
    // dependOnInheritedWidgetOfExactType is not legal in initState.
    final settings = AppScope.of(context).settings;
    _urlController.text = settings.baseUrl;
    _tokenController.text = settings.authToken;
    _usernameController.text = settings.username;
    _initialized = true;
  }

  @override
  void dispose() {
    _urlController.dispose();
    _tokenController.dispose();
    _usernameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final backend = AppScope.of(context);
    final settings = backend.settings;

    return Scaffold(
      appBar: AppBar(title: const Text('Ajustes')),
      body: ListenableBuilder(
        listenable: Listenable.merge([backend, settings]),
        builder: (context, _) {
          return ListView(
            children: [
              _SectionHeader('Backend'),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                child: TextField(
                  controller: _urlController,
                  decoration: InputDecoration(
                    labelText: 'URL del backend',
                    helperText: 'Por defecto http://127.0.0.1:8002 '
                        '(10.0.2.2 en emulador Android)',
                    errorText: _urlError,
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      icon: const Icon(Icons.save),
                      tooltip: 'Guardar',
                      onPressed: _saveUrl,
                    ),
                  ),
                  onChanged: (v) => setState(() => _urlError = settings.validateBaseUrl(v)),
                  onSubmitted: (_) => _saveUrl(),
                ),
              ),
              ListTile(
                title: const Text('Probar conexión'),
                subtitle: Text(_testing
                    ? 'Probando…'
                    : 'GET /api/system/ping en ${settings.effectiveBaseUrl}',
                    style: const TextStyle(fontSize: 11)),
                trailing: _testing
                    ? const SizedBox(
                        width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.wifi_tethering),
                onTap: _testing ? null : _testConnection,
              ),
              SwitchListTile(
                title: const Text('Permitir HTTP remoto'),
                subtitle: const Text(
                  'Sin esto solo se acepta texto plano contra loopback. '
                  'Se requiere HTTPS para cualquier otro host.',
                  style: TextStyle(fontSize: 11),
                ),
                value: settings.allowInsecureRemote,
                onChanged: (v) async {
                  await settings.setAllowInsecureRemote(v);
                  setState(() => _urlError = settings.validateBaseUrl(_urlController.text));
                },
              ),
              SwitchListTile(
                title: const Text('Conectar automáticamente'),
                subtitle: const Text('Abre /ws al lanzar la app', style: TextStyle(fontSize: 11)),
                value: settings.autoConnect,
                onChanged: (v) async {
                  await settings.setAutoConnect(v);
                  if (v) backend.connect();
                },
              ),
              _WsButton(backend: backend),

              _SectionHeader('Sincronización'),
              ListTile(
                title: const Text('Intervalo de sondeo'),
                subtitle: Text('${settings.pollIntervalSeconds}s', style: const TextStyle(fontSize: 11)),
                trailing: SizedBox(
                  width: 180,
                  child: Slider(
                    value: settings.pollIntervalSeconds.toDouble(),
                    min: 2,
                    max: 60,
                    divisions: 29,
                    label: '${settings.pollIntervalSeconds}s',
                    onChanged: (v) => settings.setPollInterval(v.round()),
                  ),
                ),
              ),
              SwitchListTile(
                title: const Text('Reenviar cola al reconectar'),
                subtitle: const Text('Reproduce la cola offline en orden FIFO',
                    style: TextStyle(fontSize: 11)),
                value: settings.replayOnReconnect,
                onChanged: settings.setReplayOnReconnect,
              ),
              SwitchListTile(
                title: const Text('Preferir sondeo en segundo plano'),
                subtitle: const Text(
                  'Cierra el socket tras 5 min en segundo plano o con batería <15%',
                  style: TextStyle(fontSize: 11),
                ),
                value: settings.preferPollingWhenIdle,
                onChanged: settings.setPreferPollingWhenIdle,
              ),

              _SectionHeader('Autenticación'),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                child: TextField(
                  controller: _usernameController,
                  decoration: const InputDecoration(
                    labelText: 'Usuario',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: TextField(
                  controller: _tokenController,
                  decoration: const InputDecoration(
                    labelText: 'Token',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: settings.setAuthToken,
                ),
              ),
              ListTile(
                title: const Text('Iniciar sesión'),
                subtitle: const Text('POST /api/auth/login', style: TextStyle(fontSize: 11)),
                trailing: const Icon(Icons.login),
                onTap: _login,
              ),
              const _AuthWarning(),

              _SectionHeader('Notificaciones'),
              _NotificationToggle(
                title: 'Tarea disponible',
                keyName: 'notifyTaskAvailable',
                value: settings.notifyTaskAvailable,
                settings: settings,
              ),
              _NotificationToggle(
                title: 'Resultado de tarea',
                keyName: 'notifyTaskResult',
                value: settings.notifyTaskResult,
                settings: settings,
              ),
              _NotificationToggle(
                title: 'Alerta del sistema',
                keyName: 'notifySystemAlert',
                value: settings.notifySystemAlert,
                settings: settings,
              ),
              _NotificationToggle(
                title: 'Cambio de estado del PC',
                keyName: 'notifyPcStateChange',
                value: settings.notifyPcStateChange,
                settings: settings,
              ),

              _SectionHeader('Identidad'),
              ListTile(
                title: const Text('device_id'),
                subtitle: Text(settings.deviceId, style: const TextStyle(fontSize: 11)),
              ),
              ListTile(
                title: const Text('agent_id'),
                subtitle: Text(settings.agentId, style: const TextStyle(fontSize: 11)),
              ),
              ListTile(
                title: const Text('Canal WebSocket'),
                subtitle: Text('${settings.wsUrl}\n${settings.channels.join(', ')}',
                    style: const TextStyle(fontSize: 11)),
              ),

              _SectionHeader('Registro'),
              _LogSection(backend: backend),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }

  void _saveUrl() {
    final settings = AppScope.of(context).settings;
    final error = settings.validateBaseUrl(_urlController.text);
    setState(() => _urlError = error);
    if (error != null) return;
    settings.setBaseUrl(_urlController.text);
    final backend = AppScope.of(context);
    backend.disconnect();
    backend.connect();
  }

  Future<void> _testConnection() async {
    setState(() => _testing = true);
    final ok = await AppScope.of(context).ping();
    if (!mounted) return;
    setState(() => _testing = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      content: Text(ok
          ? 'Backend accesible en ${AppScope.of(context).settings.effectiveBaseUrl}'
          : 'No se pudo conectar — revisa la URL y que el servidor esté en :8002'),
    ));
  }

  Future<void> _login() async {
    final backend = AppScope.of(context);
    final username = _usernameController.text.trim();
    if (username.isEmpty) return;
    final result = await backend.login(username);
    if (!mounted) return;
    if (result.isOk) {
      _tokenController.text = backend.settings.authToken;
    }
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      behavior: SnackBarBehavior.floating,
      content: Text(result.isOk
          ? 'Sesión iniciada (el token del backend aún es un placeholder)'
          : 'Login falló: ${result.error}'),
    ));
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 6),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          letterSpacing: 1.1,
          color: Colors.white38,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _WsButton extends StatelessWidget {
  const _WsButton({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: backend,
      builder: (context, _) => ListTile(
        title: Text(backend.isConnected ? 'Desconectar' : 'Conectar'),
        subtitle: Text(backend.state.name, style: const TextStyle(fontSize: 11)),
        trailing: Icon(backend.isConnected ? Icons.link_off : Icons.link),
        onTap: backend.isConnected ? backend.disconnect : backend.connect,
      ),
    );
  }
}

class _NotificationToggle extends StatelessWidget {
  const _NotificationToggle({
    required this.title,
    required this.keyName,
    required this.value,
    required this.settings,
  });

  final String title;
  final String keyName;
  final bool value;
  final SettingsService settings;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile(
      title: Text(title),
      value: value,
      onChanged: (v) => settings.setNotificationToggle(keyName, v),
    );
  }
}

class _AuthWarning extends StatelessWidget {
  const _AuthWarning();

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.orange.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          Icon(Icons.warning_amber, size: 16, color: Colors.orangeAccent),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'El backend no valida el token todavía: /api/auth/login devuelve un '
              'placeholder y no hay middleware de auth. No expongas el puerto 8002 '
              'a la red hasta que se implemente.',
              style: TextStyle(fontSize: 11, color: Colors.white70),
            ),
          ),
        ],
      ),
    );
  }
}

class _LogSection extends StatelessWidget {
  const _LogSection({required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    final entries = backend.recentLogs(limit: 50);
    return ExpansionTile(
      leading: const Icon(Icons.receipt_long),
      title: const Text('Registro'),
      children: [
        if (entries.isEmpty)
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('Sin entradas', style: TextStyle(fontSize: 12, color: Colors.white38)),
          ),
        for (final e in entries)
          ListTile(
            dense: true,
            title: Text(e.message, style: const TextStyle(fontSize: 11)),
            subtitle: Text(e.level, style: const TextStyle(fontSize: 9)),
          ),
      ],
    );
  }
}
