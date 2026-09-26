# Integración Godot - AURA Desktop

## Requisitos
- Godot 4.6 (`C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe`)
- Backend AURA corriendo en `http://localhost:8000`

## Estructura del proyecto
```
godot/
├── project.godot
├── export_presets.cfg
├── scenes/
│   ├── main/Main.tscn
│   ├── ui/ChatUI.tscn
│   ├── ui/RadarUI.tscn
│   └── ui/EarthquakeUI.tscn
├── scripts/
│   ├── network/aura_client.gd
│   ├── network/event_bus.gd
│   ├── ui/chat_panel.gd
│   ├── ui/jjk_theme.gd
│   ├── ui/radar_panel.gd
│   ├── ui/earthquake_panel.gd
│   ├── ui/settings_panel.gd
│   ├── gesture/gesture_controller.gd
│   ├── audio/voice_engine.gd
│   └── 3d/particle_system.gd
├── assets/shaders/
└── plugins/
```

## Verificación del proyecto (headless)
```bash
"C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe" --headless --check-only --path godot --quit
```
Resultado esperado: `True` / `EXIT:` sin errores.

## Exportación (pasos verificados)
Godot headless no exporta `.exe`/`.pck` sin plantillas instaladas. Hacerlo desde el editor:

1. Abrir proyecto: `AURA_Build.bat` o ejecutar Godot portable con `--path godot --editor`
2. Ir a **Project > Export**
3. Agregar preset **Windows Desktop**
4. Exportar a `dist/AURA_Desktop.exe`
5. Empaquetar: `dist/AURA_Desktop_v1.0.0.zip`

### Contenido del `.zip` de distribución
- `AURA_Desktop.exe` - build exportado
- `Godot_v4.6-stable_win64.exe` - portable para re-exportar
- `AURA_Build.bat` - lanzador del editor
- `docs/` - documentación
- `backend/` - código del backend

## Conexión con backend
- `AuraClient` se conecta a `http://localhost:8000`
- Endpoints usados:
  - `POST /api/chat`
  - `GET /api/gesture/stream`
  - `GET /api/wifi/scan`
  - `GET /api/earthquakes/recent`

## Correcciones aplicadas en Fase 17
- `event_bus.gd`: agregada señal `stream_token`
- `aura_client.gd`: emite `EventBus.stream_token` en vez de señal propia
- `chat_panel.gd`: removido `bbcode_enabled` (no existe en Godot 4.6)
- `chat_panel.gd`: removido `autowrap_mode` obsoleto en labels dinámicos
- `earthquake_panel.gd`: tipado explícito `float` en `clamp()` para evitar parse error
- `earthquake_panel.gd`: null check en `_update_3d_visuals()` si falta `Eq3D`
- `radar_panel.gd`: null check en `_update_3d_radar()` si falta `Radar3D`
- `EarthquakeUI.tscn`: agregado script `earthquake_panel.gd` y nodos `Eq3D`, `TimelineList`
- `export_presets.cfg`: agregado con preset Windows válido
- Limpiado cache `.godot/`

## Plugins
Los plugins van en `godot/plugins/` con un `manifest.json`.
Ejemplo: `plugins/hello_world/`
