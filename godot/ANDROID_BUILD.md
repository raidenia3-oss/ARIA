# AURA - Android Build Guide

## Requisitos

- Godot 4.6 (export templates instalados)
- Android SDK en `C:\Users\User\AppData\Local\Android\Sdk`
- Android NDK r25+ en `C:\Users\User\AppData\Local\Android\Sdk\ndk\25.1.8937393`
- Java JDK 17 o 21
- `build_android.bat` preparado

## Setup rápido

1. Ejecutá `godot\setup_android.bat` para verificar el entorno.
2. Si falta NDK, instalalo desde Android Studio:
   - SDK Manager → SDK Tools → NDK (Side-by-side) → marcar `25.1.8937393`
3. Abrí `godot\project.godot` en Godot y usá **Project → Export → Android** para generar el APK/AAB.

## Build manual

```bat
cd C:\Users\User\Downloads\AURA\godot
build_android.bat
```

## Notas

- `export_presets.cfg` ya tiene configurado el preset Android, keystore debug y rutas de íconos.
- Los íconos están en `godot/android/icons/`.
- Si exportás desde Godot, recordá seleccionar el preset Android y el destino en `dist/`.
