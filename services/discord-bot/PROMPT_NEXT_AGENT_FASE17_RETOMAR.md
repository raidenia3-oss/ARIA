# Prompt para próxima sesión — Fase 17 Godot / Build real

## Contexto previo
- El proyecto AURA tiene backend FastAPI funcionando, frontend web, y un cliente Godot 4.3/4.6 en `godot/`.
- Ya se pulizó código, pero el build aún NO está verificado ni empaquetado.
- Godot 4.6 está instalado en: `C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe`
- Working dir: `C:\Users\User\Downloads\AURA`

## Estado actual de Godot
- Proyecto ya valida escenas en `godot/`, scripts en `godot/scripts/**/*.gd`, shaders en `godot/assets/shaders/`.
- Quedó 1 error activo en `godot --headless --check-only`:
  - `chat_panel.gd` se conecta a `EventBus.stream_token`, pero ese signal no existe en `event_bus.gd`.
- Hay referencias a nodos 3D que pueden no existir en las escenas UI (`Radar3D`, `Eq3D`).
- Ya se eliminaron nodos `[node name="Script" ...]` inválidos y se ajustó `project.godot`.
- EventBus es autoload, sin `class_name`.

## Objetivo de la próxima sesión
1. Correr `godot --headless --check-only --path godot` y dejar el proyecto 100% limpio.
2. Ajustar escenas y scripts para que Godot 4.6 no tire errores de parseo ni de runtime en `_ready()`.
3. Probar exportación real:
   - Windows Desktop
   - Linux Desktop (si aplica)
4. Empaquetar en `dist/AURA_Desktop_v1.0.0.zip`.
5. Actualizar `docs/godot-integration.md` con pasos verificados.

## Restricciones
- No modifiques `docs/training/strategy.md`, `services/discord-bot/PROMPT_NEXT_AGENT*.md`.
- No subas secrets.
- Si algo falla en el build, reportá el error exacto y corregí antes de seguir.

## Checklist de entrada
- Ejecutar Godot headless desde la ruta conocida.
- Leer `godot/scripts/ui/chat_panel.gd`, `godot/scripts/network/event_bus.gd`, `godot/scripts/ui/radar_panel.gd`, `godot/scripts/ui/earthquake_panel.gd`.
- Leer escenas: `godot/scenes/ui/ChatUI.tscn`, `RadarUI.tscn`, `EarthquakeUI.tscn`, `Main.tscn`.
- Corregir solo lo imprescindible para que `check-only` pase.
