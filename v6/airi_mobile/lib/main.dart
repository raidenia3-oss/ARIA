import 'package:flutter/material.dart';

import 'screens/command.dart';
import 'screens/dashboard.dart';
import 'screens/settings.dart';
import 'services/backend_service.dart';
import 'services/notification_service.dart';
import 'services/offline_queue.dart';
import 'services/settings_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Settings first: the notification service reads its per-type toggles, and
  // the backend derives its URLs from the base URL.
  final settings = await SettingsService.open();
  final notifications = NotificationService(settings);
  await notifications.init();

  final queue = await OfflineQueue.open();
  final backend = BackendService(
    settings: settings,
    queue: queue,
    notifications: notifications,
  );
  await backend.init();

  runApp(AiriApp(backend: backend));
}

/// Dependency scope. A plain [InheritedNotifier] keeps the project free of a
/// state-management package.
class AppScope extends InheritedNotifier<BackendService> {
  const AppScope({
    super.key,
    required BackendService backend,
    required super.child,
  }) : super(notifier: backend);

  static BackendService of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope not found in the widget tree');
    return scope!.notifier!;
  }

  SettingsService get settings => notifier!.settings;

  OfflineQueue get queue => notifier!.queue;
}

class AiriApp extends StatelessWidget {
  const AiriApp({super.key, required this.backend});

  final BackendService backend;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      backend: backend,
      child: MaterialApp(
        title: 'ARIA',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF22D3EE),
            brightness: Brightness.dark,
          ),
          scaffoldBackgroundColor: const Color(0xFF0A0E27),
          cardTheme: const CardTheme(
            elevation: 0,
            margin: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          ),
        ),
        home: const HomeShell(),
      ),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> with WidgetsBindingObserver {
  int _index = 0;
  BackendService? _backend;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _backend ??= AppScope.of(context);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) return;
    final backend = _backend;
    if (backend == null) return;
    // iOS tears down the socket when the app is suspended; reconnect eagerly
    // on resume, then pull a full snapshot (spec §1.5).
    if (!backend.isConnected) backend.connect();
    backend.refreshAll();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: const [
          DashboardScreen(),
          CommandScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: ListenableBuilder(
        listenable: AppScope.of(context),
        builder: (context, _) {
          final backend = AppScope.of(context);
          return NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: [
              const NavigationDestination(
                icon: Icon(Icons.dashboard_outlined),
                selectedIcon: Icon(Icons.dashboard),
                label: 'Estado',
              ),
              NavigationDestination(
                icon: Badge(
                  isLabelVisible: backend.queue.pendingCount > 0,
                  label: Text('${backend.queue.pendingCount}'),
                  child: const Icon(Icons.terminal_outlined),
                ),
                selectedIcon: const Icon(Icons.terminal),
                label: 'Comandos',
              ),
              const NavigationDestination(
                icon: Icon(Icons.settings_outlined),
                selectedIcon: Icon(Icons.settings),
                label: 'Ajustes',
              ),
            ],
          );
        },
      ),
    );
  }
}
