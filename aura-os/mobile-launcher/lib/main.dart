import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:http/http.dart' as http;
import 'dart:async';
import 'dart:convert';
import 'dart:math';

void main() {
  // Global error boundary — catch unhandled Flutter errors
  FlutterError.onError = (FlutterErrorDetails details) {
    FlutterError.dumpErrorToConsole(details);
    // Log to backend if remote mode
  };

  runApp(const AuraLauncherApp());
}

// ─── Termux Service ──────────────────────────────────────────────────────────

class TermuxService {
  /// Runs a command in Termux environment and returns output.
  static Future<String> runCommand(String command) async {
    const baseUrl = String.fromEnvironment('AURA_API_URL', defaultValue: 'http://localhost:8000');
    final response = await http.post(
      Uri.parse('$baseUrl/api/mobile/termux/cmd'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'command': command}),
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['output'] ?? 'No output';
    }
    return 'Error: ${response.statusCode}';
  }

  /// Starts the local AURA backend inside Termux/proot-distro.
  static Future<bool> startLocalBackend() async {
    try {
      await runCommand('python ~/AURA/backend/main.py --port 8000 &');
      return true;
    } catch (e) {
      return false;
    }
  }

  /// Checks whether proot-distro Ubuntu is installed.
  static Future<bool> isLinuxInstalled() async {
    final output = await runCommand('proot-distro list');
    return output.contains('ubuntu');
  }
}

// ─── Sync Service ────────────────────────────────────────────────────────────

class AuraSyncService {
  WebSocketChannel? _channel;
  final String _wsUrl;
  final Function(Map<String, dynamic>)? onTelemetry;
  final VoidCallback? onConnected;

  AuraSyncService({
    required String wsUrl,
    this.onTelemetry,
    this.onConnected,
  })  : _wsUrl = wsUrl;

  void connect() {
    _channel = WebSocketChannel.connect(Uri.parse(_wsUrl));
    _channel!.stream.listen((message) {
      final data = jsonDecode(message) as Map<String, dynamic>;
      onTelemetry?.call(data);
    }, onError: (e) {
      // auto-reconnect with backoff handled by caller
    }, onDone: () {
      onConnected?.call();
    });
  }

  void syncAction(String action, {Map<String, dynamic>? data}) {
    _channel?.sink.add(jsonEncode({'action': action, 'data': data ?? {}}));
  }

  void disconnect() {
    _channel?.sink.close();
    _channel = null;
  }
}

// ─── Connection Manager (exponential backoff reconnect) ────────────────────────

class ConnectionManager {
  WebSocketChannel? _channel;
  final String wsUrl;
  final Function(Map<String, dynamic>)? onTelemetry;
  final VoidCallback? onConnected;
  final Function(String)? onError;

  Timer? _reconnectTimer;
  int _attemptCount = 0;
  static const int _maxDelaySec = 300;
  bool _connecting = false;

  ConnectionManager({
    required this.wsUrl,
    this.onTelemetry,
    this.onConnected,
    this.onError,
  });

  void connect() {
    if (_connecting || _channel != null) return;
    _connecting = true;
    _attemptCount = 0;

    _doConnect();
  }

  void _doConnect() {
    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _channel!.stream.listen(
        (message) {
          _attemptCount = 0; // Reset on successful message
          final data = jsonDecode(message) as Map<String, dynamic>;
          onTelemetry?.call(data);
        },
        onError: (e) {
          _channel = null;
          onError?.call('connection_error: $e');
          _scheduleReconnect();
        },
        onDone: () {
          _channel = null;
          _scheduleReconnect();
          onConnected?.call(); // Triggers reconnect in UI
        },
      );
      _connecting = false;
    } catch (e) {
      _channel = null;
      _connecting = false;
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _attemptCount = (_attemptCount + 1).clamp(0, 10);
    final delay = pow(2, _attemptCount).toInt().clamp(1, _maxDelaySec);

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: delay), () {
      if (_channel == null) {
        _doConnect();
      }
    });
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _channel?.sink.close();
    _channel = null;
    _connecting = false;
    _attemptCount = 0;
  }
}

// ─── App Entry ───────────────────────────────────────────────────────────────

class AuraLauncherApp extends StatelessWidget {
  const AuraLauncherApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AURA Launcher',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0a0e27)),
        brightness: Brightness.dark,
        useMaterial3: true,
      ),
      home: const AuraHomePage(),
    );
  }
}

// ─── Mode Enum ────────────────────────────────────────────────────────────────

enum LauncherMode { localLinux, remoteDesktop }

// ─── Mode Toggle Widget ───────────────────────────────────────────────────────

class ModeToggle extends StatelessWidget {
  final LauncherMode currentMode;
  final ValueChanged<LauncherMode> onModeChanged;
  final bool isTermuxReady;

  const ModeToggle({
    super.key,
    required this.currentMode,
    required this.onModeChanged,
    required this.isTermuxReady,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0xFF1a1f3a),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        children: [
          _buildModeButton(
            LauncherMode.localLinux,
            'Local Linux',
            Icons.terminal,
            isTermuxReady ? Colors.green : Colors.orange,
          ),
          const SizedBox(width: 8),
          _buildModeButton(
            LauncherMode.remoteDesktop,
            'Remote Desktop',
            Icons.computer,
            const Color(0xFF6366f1),
          ),
        ],
      ),
    );
  }

  Widget _buildModeButton(
    LauncherMode mode,
    String label,
    IconData icon,
    Color color,
  ) {
    final isSelected = currentMode == mode;
    return GestureDetector(
      onTap: () => onModeChanged(mode),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? color.withOpacity(0.3) : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isSelected ? color : Colors.white10,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: color, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}

// ─── Main Page ────────────────────────────────────────────────────────────────

class AuraHomePage extends StatefulWidget {
  const AuraHomePage({super.key});

  @override
  State<AuraHomePage> createState() => _AuraHomePageState();
}

class _AuraHomePageState extends State<AuraHomePage> {
  final TextEditingController _controller = TextEditingController();
  final List<ChatMessage> _messages = [];
  final String _backendUrl = "http://aura-os.local:8000";
  late ConnectionManager _connectionManager;
  bool _connected = false;

  LauncherMode _currentMode = LauncherMode.remoteDesktop;
  bool _isTermuxReady = false;
  bool _showTerminal = false;
  final TermuxService _termux = TermuxService();

  @override
  void initState() {
    super.initState();
    _connectionManager = ConnectionManager(
      wsUrl: '$_backendUrl/ws/mobile/sync/mobile-launcher',
      onTelemetry: (data) {
        if (data['type'] == 'telemetry') {
          // Process telemetry data
        }
      },
      onConnected: () {
        // Connection established or reconnected
      },
      onError: (error) {
        setState(() => _connected = false);
      },
    );
    _connectToBackend();
    _checkTermux();
  }

  @override
  void dispose() {
    _connectionManager.disconnect();
    _controller.dispose();
    super.dispose();
  }

  void _checkTermux() async {
    final ready = await _termux.isLinuxInstalled();
    setState(() => _isTermuxReady = ready);
  }

  void _connectToBackend() async {
    try {
      final response = await http.get(Uri.parse("$_backendUrl/api/health"));
      if (response.statusCode == 200) {
        setState(() => _connected = true);
        _connectionManager.connect();
      } else {
        setState(() => _connected = false);
        _connectionManager.connect();
      }
    } catch (e) {
      setState(() => _connected = false);
      _connectionManager.connect();
    }
  }

  void _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;

    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true));
    });
    _controller.clear();

    try {
      final response = await http.post(
        Uri.parse("$_backendUrl/api/chat"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"prompt": text, "session_id": "mobile-launcher", "user_id": "mobile"}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final reply = data["text"] ?? "Sin respuesta";
        setState(() {
          _messages.add(ChatMessage(text: reply, isUser: false));
        });
      }
    } catch (e) {
      setState(() {
        _messages.add(ChatMessage(text: "Error de conexión: $e", isUser: false));
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0a0e27),
      appBar: AppBar(
        title: const Text("AURA Launcher"),
        backgroundColor: const Color(0xFF0a0e27),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: ModeToggle(
              currentMode: _currentMode,
              onModeChanged: (mode) {
                setState(() {
                  _currentMode = mode;
                  if (mode == LauncherMode.localLinux) {
                    _termux.startLocalBackend();
                  }
                });
              },
              isTermuxReady: _isTermuxReady,
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            color: const Color(0xFF0a0e27),
            child: Row(
              children: [
                Icon(_connected ? Icons.wifi : Icons.wifi_off,
                    color: _connected ? Colors.green : Colors.red),
                const SizedBox(width: 8),
                Text(
                  _connected ? "Conectado a AURA" : "Sin conexión",
                  style: const TextStyle(color: Colors.white),
                ),
                const Spacer(),
                Icon(_isTermuxReady ? Icons.security : Icons.security,
                    color: _isTermuxReady ? Colors.green : Colors.orange,
                    size: 16),
                const SizedBox(width: 4),
                Text(
                  _isTermuxReady ? "Linux local listo" : "Linux no disponible",
                  style: TextStyle(
                      color: _isTermuxReady ? Colors.green : Colors.orange,
                      fontSize: 12),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                return Align(
                  alignment: msg.isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: msg.isUser
                          ? const Color(0xFF1a1f3a)
                          : const Color(0xFF2a1f3a),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text(msg.text,
                        style: const TextStyle(color: Colors.white)),
                  ),
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: _currentMode == LauncherMode.localLinux
                          ? "Comando Linux..."
                          : "Escribe a AURA...",
                      hintStyle: const TextStyle(color: Colors.white54),
                      border: const OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                if (_currentMode == LauncherMode.localLinux)
                  IconButton(
                    onPressed: _isTermuxReady
                        ? () async {
                            final cmd = _controller.text.trim();
                            if (cmd.isNotEmpty) {
                              final output = await _termux.runCommand(cmd);
                              setState(() {
                                _messages.add(
                                    ChatMessage(text: '\$ $cmd', isUser: true));
                                _messages.add(ChatMessage(
                                    text: output, isUser: false));
                              });
                              _controller.clear();
                            }
                          }
                        : null,
                    icon: const Icon(Icons.terminal, color: Colors.white70),
                  )
                else
                  IconButton(
                    onPressed: _sendMessage,
                    icon: const Icon(Icons.send, color: Colors.white),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
