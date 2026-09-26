# Prompt para Cline: Fase 15 - Godot Frontend 3D Nativo (Base de App Desktop)

## Contexto
Fases 1-14 completadas. El backend AURA ya funciona como API/WebSocket. Ahora el objetivo es reemplazar/convertir el frontend Next.js en una **app de escritorio nativa con Godot 4** que actúe como interfaz principal, manteniendo toda la funcionalidad actual y sumando capacidades 3D nativas.

Razón: evitar dependencias de navegador, Railway/Render y hosting web. Godot empaqueta a Windows/Mac/Linux/Android/iOS desde un solo proyecto.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Godot 4.x instalado en el sistema
- Backend FastAPI corriendo en `http://localhost:8000`
- Node.js/Next.js existente se mantiene como fallback web por ahora

## Tareas

### 1. Estructura del proyecto Godot
- Crear `godot/` en la raíz con proyecto Godot 4.x
- Organización:
  - `godot/scenes/` — escenas principales
  - `godot/scripts/` — scripts GDScript
  - `godot/assets/` — fuentes, texturas, shaders
  - `godot/addons/` — plugins del marketplace o custom
- Crear escenas base:
  - `res://scenes/main/Main.tscn` — nodo raíz, manejo de ciclo de vida
  - `res://scenes/ui/ChatUI.tscn` — panel de chat 3D
  - `res://scenes/ui/RadarUI.tscn` — panel WiFi radar 3D
  - `res://scenes/ui/EarthquakeUI.tscn` — panel sísmico 3D
  - `res://scenes/3d/ParticleWorld.tscn` — mundo 3D para partículas

### 2. Conexión Godot <-> Backend AURA
- Crear `godot/scripts/network/aura_client.gd`:
  - Cliente HTTP para `/api/chat`, `/api/chat/stream`, `/api/gesture/detect`, `/api/wifi/scan`, `/api/earthquakes/recent`
  - Cliente WebSocket para `/api/gesture/stream` y `/api/mesh/stream` (si aplica)
  - Manejo de reconexión automática
  - Cola de mensajes pendientes si el backend no está disponible
- Crear `godot/scripts/network/event_bus.gd` (singleton):
  - Bus de eventos global para desacoplar UI de red
  - Señales: `chat_received`, `gesture_detected`, `wifi_update`, `earthquake_alert`, `connection_lost`

### 3. Chat 3D en Godot
- `godot/scripts/ui/chat_panel.gd` attached a `ChatUI.tscn`:
  - Panel 3D flotante con estilo JJK (colores oscuros, bordes cyan/purple glow)
  - Input de texto 3D con cursor parpadeante
  - Lista de mensajes con scroll 3D
  - Indicador de proveedor (Local/Cloud) y modelo usado
  - Botones de feedback (👍/👎) como objetos 3D clickeables
  - Streaming de respuesta: mostrar tokens a medida que llegan
- Integrar con `aura_client.gd` para enviar/recibir mensajes

### 4. Partículas 3D nativas en Godot
- `godot/scripts/3d/particle_system.gd`:
  - Usar `GPUParticles3D` de Godot para efectos de alta performance
  - Efectos: `explosion`, `implosion`, `vortex`, `beam`, `aura`, `stream`, `domain_expansion`
  - Shaders custom para glow, pulsos, cursed energy
  - Máximo 5000 partículas por efecto
  - Colores JJK: purple `#7c4dff`, cyan `#00e5ff`, cursed energy `#8a2be2`, red `#ff4d4d`
- `godot/scripts/3d/gesture_fx.gd`:
  - Conectar detección de gestos con efectos de partículas
  - Mapeo:
    - `open_hand` → explosion
    - `fist` → implosion
    - `peace` → vortex
    - `index` → beam
    - `heart` → aura
    - `swipe` → stream

### 5. Gestos por cámara en Godot
- `godot/scripts/gesture/camera_tracker.gd`:
  - Capturar video desde cámara web (usando `CameraFeed` de Godot o plugin)
  - Si Godot no tiene acceso directo a cámara, usar módulo Python externo o puerto UDP para enviar frames al backend `/api/gesture/detect`
  - Mostrar feed de cámara como textura en un `QuadMesh3D` en el mundo 3D
  - Overlay de landmarks y gestos detectados
- `godot/scripts/gesture/gesture_controller.gd`:
  - Recibir eventos de gestos desde `event_bus.gd`
  - Mapear gestos a acciones en la UI:
    - `fist` → detener generación
    - `index` → seleccionar elemento
    - `peace` → confirmar
    - `open_hand` → enviar mensaje
    - `heart` → feedback up
    - `swipe` → limpiar chat
  - Trigger de efectos de partículas según gesto

### 6. Estilo JJK en toda la UI de Godot
- `godot/scripts/ui/jjk_theme.gd` (autoload):
  - Paleta de colores JJK: BG `#05070a`, PANEL `#0f1219`, ACCENT `#7c4dff`, ACCENT2 `#00e5ff`, TEXT `#e6e9f0`, CURSED_ENERGY `#8a2be2`
  - Funciones helper para aplicar estilos a controles 3D/2D
  - Efectos de glow usando `StyleBoxFlat` con bordes y sombras
  - Animaciones de transición usando `Tween`
- Aplicar a:
  - `ChatUI.tscn`
  - `RadarUI.tscn`
  - `EarthquakeUI.tscn`
  - Menús principales

### 7. Audio y Voz (fase inicial, sin cloud)
- `godot/scripts/audio/voice_engine.gd`:
  - STT local: usar Whisper tiny/base local via HTTP al backend o módulo Python
  - TTS local: integrar Piper TTS (https://github.com/rhasspy/piper) como proceso externo o DLL
    - Voces femeninas disponibles en Piper (ej. `es_ES-davefx-medium` o similares)
    - Generar audio WAV y reproducirlo en Godot con `AudioStreamPlayer`
  - Wake word: detección simple de "hey aura" usando:
    - Opción A: enviar audio al backend para procesamiento
    - Opción B: modelo tiny local de wake word si es posible
  - No depender de ElevenLabs ni APIs cloud para voz básica
- UI de voz:
  - Botón de micrófono 3D en el chat
  - Visualizador de audio (ondas) mientras habla
  - Indicador de "escuchando..." y "procesando..."

### 8. Plugins Marketplace (local)
- `godot/scripts/plugins/plugin_manager.gd`:
  - Escanear directorio `plugins/` en busca de scripts GDScript o escenas
  - Cada plugin tiene un manifiesto JSON: `name`, `version`, `description`, `author`, `main_scene`
  - Cargar/descargar plugins en runtime
  - Aislar plugins en árbol de escenas separado para evitar conflictos
- `godot/plugins/` con ejemplos:
  - `hello_world/` — plugin mínimo
  - `gesture_effect/` — efecto de partículas custom
  - `voice_command/` — comando de voz custom
- UI de plugins:
  - Panel 3D para listar/instalar/desinstalar plugins
  - Botones de enable/disable

### 9. Integración con WiFi Radar y Terremotos en Godot
- `godot/scripts/ui/radar_panel.gd` attached a `RadarUI.tscn`:
  - Visualización 3D del mapa de calor WiFi en un plano con shader
  - Puntos de acceso como esferas con altura = intensidad RSSI
  - Actualización en tiempo real desde `/api/wifi/stream`
- `godot/scripts/ui/earthquake_panel.gd` attached a `EarthquakeUI.tscn`:
  - Mapa 3D del mundo con terremotos como marcadores
  - Tamaño = magnitud, color = profundidad
  - Timeline de eventos
  - Alertas visuales cuando `risk_level` es high/critical

### 10. Build y empaquetado
- Crear `godot/export/` con plantillas de exportación:
  - `windows desktop` — `.exe` standalone
  - `linux desktop` — binario
  - `macos desktop` — `.app`
  - `android` — `.apk` (gestos con cámara móvil)
- Configurar `export_presets.cfg` en el proyecto Godot
- Crear `scripts/build_godot.bat` y `scripts/build_godot.sh` para compilar desde línea de comandos
- El ejecutable debe poder correr el backend embebido o conectarse a uno externo

## Reglas
- NO modifiques `docs/training/strategy.md`, `services/discord-bot/PROMPT_NEXT_AGENT*.md`
- NO subas secrets
- Godot 4.x usa GDScript; si necesitas lógica compleja, puedes invocar el backend Python
- Mantén comunicación con el backend existente via HTTP/WebSocket; no dupliques lógica de negocio en Godot
- Si no tienes experiencia en Godot, crea la estructura base y scripts mínimos; los detalles de pulido se harán después
- Usa `print()` en GDScript solo para debug; en producción usa el logger de Godot

## Entregables
1. `godot/project.godot` — proyecto Godot 4.x inicial
2. `godot/scenes/main/Main.tscn` y `main_loop.gd`
3. `godot/scenes/ui/ChatUI.tscn` y `chat_panel.gd`
4. `godot/scenes/ui/RadarUI.tscn` y `radar_panel.gd`
5. `godot/scenes/ui/EarthquakeUI.tscn` y `earthquake_panel.gd`
6. `godot/scenes/3d/ParticleWorld.tscn` y `particle_system.gd`
7. `godot/scripts/network/aura_client.gd` y `event_bus.gd`
8. `godot/scripts/gesture/camera_tracker.gd` y `gesture_controller.gd`
9. `godot/scripts/audio/voice_engine.gd`
10. `godot/scripts/ui/jjk_theme.gd`
11. `godot/scripts/plugins/plugin_manager.gd`
12. `godot/plugins/hello_world/` — plugin de ejemplo
13. `scripts/build_godot.bat` y `scripts/build_godot.sh`
14. `docs/godot-integration.md` — guía de setup y conexión backend

## Validación final
1. Abrir proyecto en Godot 4.x y verificar que no haya errores de importación
2. Ejecutar escena `Main.tscn` y verificar que la UI carga
3. Conectar backend (`uvicorn ame_backend.src.main:app --reload`)
4. En Godot, enviar mensaje de chat y verificar respuesta del backend
5. Verificar que los estilos JJK se aplican correctamente
6. Verificar que el sistema de partículas renderiza en 3D
7. Exportar build de prueba y verificar que el ejecutable funciona
