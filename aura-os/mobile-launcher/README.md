# AURA Mobile Launcher

Launcher móvil para AURA OS. Conecta el asistente virtual con la PC principal via WebSocket/REST.

## Características
- Chat con AURA desde el móvil
- Sincronización en tiempo real con el desktop
- Notificaciones push del sistema
- Control de gestures (integración con gesture-control)
- Actualizaciones automáticas desde la PC

## Stack
- Frontend: Flutter Web / PWA
- Backend: Conexión a `http://aura-os.local:8000`
- Sync: Redis Pub/Sub + WebSockets
- Discovery: mDNS/Bonjour

## Estructura
```
mobile-launcher/
├── lib/                    # Código Flutter
├── assets/                 # Recursos
├── pubspec.yaml
└── README.md
```

## Instalación
```bash
cd aura-os/mobile-launcher
flutter pub get
flutter run
```

## Build
```bash
flutter build apk --release
flutter build ios --release
```

## Web
```bash
flutter build web
```

## Conexión
El launcher se conecta automáticamente a `http://aura-os.local:8000` via mDNS.
Si no encuentra la PC, permite ingresar la IP manualmente.
