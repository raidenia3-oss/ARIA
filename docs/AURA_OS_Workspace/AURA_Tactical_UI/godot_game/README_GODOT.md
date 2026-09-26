# AURA Godot HUD — Guía de Setup y Exportación

## Estado actual

- Cliente WebSocket (`NetworkController.gd`) implementado en GDScript 4.2
- Autoloads configurados: `AURABridge`, `GameState`, `NetworkController`
- Shader de glow creado en `shaders/core_glow.gdshader`
- Escena HUD adaptada en `scenes/HUD.tscn` con layout Sci-Fi

## Requisitos

1. **Godot 4.2+** (preferiblemente 4.2.2 o superior)
    - Descargar de: https://godotengine.org/download
    - Extraer y agregar la carpeta `bin/` al PATH
2. **Python 3.11+** (ya disponible en el sistema)
3. **Backend AURA WS** corriendo en `localhost:3000`

## Instalación rápida (Windows)

```powershell
# Descargar Godot portable
$version = "4.2.2"
$url = "https://github.com/godotengine/godot/releases/download/$version/Godot_v${version}-stable_win64.exe.zip"
Invoke-WebRequest -Uri $url -OutFile "$env:TEMP\godot.zip"
Expand-Archive "$env:TEMP\godot.zip" "$env:TEMP\godot"
$env:Path += ";$env:TEMP\godot\Godot_v${version}-stable_win64"
```

## Pasos siguientes

1. **Abrir proyecto en Godot Editor**
    - Ejecutar: `godot.exe godot_game/project.godot`
    - Godot descargará/importará automáticamente los recursos

2. **Configurar ruta del shader**
    - Seleccionar nodo `CoreMesh` en HUD.tscn
    - En Inspector > Surface > Material > New ShaderMaterial
    - En Shader > New Shader > Cargar `shaders/core_glow.gdshader`
    - Ajustar `glow_intensity` a 2.0 para efecto brillante

3. **Conectar backend WebSocket**

    ```gdscript
    # En HUD.gd, línea ~15, tras suscripciones:
    AURABridge.subscribe("node_update")
    AURABridge.subscribe("task_update")
    # Añadir también:
    AURABridge.subscribe("task_assigned")
    ```

4. **Probar en editor**
    - Presionar F5 para ejecutar
    - Verificar conexión en consola: `[NetworkController] Conectado...`
    - El núcleo 3D debe rotar y pulsar

5. **Exportar APK**
    - Proyecto > Exportar > Android
    - Configurar keystore (si no tienes, genera una nueva)
    - Exportar Debug APK a: `dist/android/app-debug-aura-hud.apk`

## Troubleshooting

### Error: "Module not found: core"

Verificar que `NetworkController.gd` está en `res://scripts/` y registrado como autoload.

### Shader no compila

Asegurarse de que el archivo tiene extensión `.gdshader` y `shader_type spatial;` en la primera línea.

### WebSocket no conecta

- Verificar que `AME_Core/ws_server.py` está corriendo en puerto 3000
- Si no, ejecutar: `cd AME_Core && python ws_server.py &`
- El cliente Godot se reconectará automáticamente cada 2s

## Estructura objetivo

```
AURA Tactics/
├── godot_game/
│   ├── project.godot (conectado a .env)
│   ├── scripts/
│   │   ├── NetworkController.gd (cliente WS)
│   │   └── HUD.gd (lógica Sci-Fi)
│   ├── autoloads/
│   │   ├── AURABridge.gd (puente global)
│   │   └── GameState.gd (estado RPG)
│   ├── scenes/
│   │   └── HUD.tscn (interfaz gráfica)
│   ├── shaders/
│   │   └── core_glow.gdshader (efecto neón)
│   └── README_GODOT.md
├── AME_Core/
│   └── ws_server.py (servidor WS en :3000)
└── AME_ECOSYSTEM/
    └── ame_app_android/ (APK complemento)
```
