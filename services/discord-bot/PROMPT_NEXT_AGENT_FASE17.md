# Prompt para Cline: Fase 17 - Empaquetado Real, Pruebas Godot y App Nativa Funcional

## Contexto
Fases 1-16 completadas. El proyecto Godot está pulido y estructurado, pero NO se ha probado abriéndolo en Godot 4.3, ni se ha generado un build real. Esta fase cierra esa deuda y entrega una app ejecutable.

## Entorno
- Working directory: `C:\Users\User\Downloads\AURA`
- Godot 4.3+ instalado en el sistema
- Backend FastAPI puede estar corriendo en `http://localhost:8000`
- Windows 10/11

## Tareas

### 1. Verificar proyecto Godot desde CLI
- Ejecutar Godot en modo headless para validar escenas:
  ```bash
  godot --headless --check-only --path godot
  ```
- Si hay errores de importación, nodos faltantes o scripts duplicados, corregirlos
- Verificar que todas las escenas referencien scripts existentes
- Verificar que `project.godot` tenga formato válido

### 2. Corregir errores de escenas/scripts encontrados
- Errores comunes esperados:
  - Referencias a nodos que no existen en la escena
  - Scripts con sintaxis GDScript inválida
  - UIDs duplicados o inválidos
  - Materiales/shaders no encontrados
- Corregir archivo por archivo hasta que `godot --check-only` pase sin errores

### 3. Crear preset de exportación real
- En `godot/export/export_presets.cfg`, crear presets para:
  - Windows Desktop (x86_64)
  - Linux Desktop (x86_64)
  - macOS (universal si es posible)
- Configurar:
  - `export_filter="all_resources"`
  - `encrypt_pck=false` (por ahora, para depuración)
  - `executable_name="AURA Desktop"`
  - `product_name="AURA Desktop"`
  - `company_name="AURA"`

### 4. Probar build desde línea de comandos
- Ejecutar:
  ```bash
  godot --export "Windows Desktop" --headless --path godot
  ```
- Si falla, corregir errores y reintentar
- El ejecutable debe quedar en `build/windows/AURA Desktop.exe`
- Verificar que el ejecutable se cree sin errores

### 5. Crear script de empaquetado final
- Mejorar `scripts/build_godot.bat` para:
  - Detectar Godot automáticamente en rutas comunes:
    - `C:\Program Files\Godot\Godot4.exe`
    - `C:\Program Files (x86)\Godot\Godot4.exe`
    - `godot` en PATH
  - Ejecutar exportación con el preset correcto
  - Mostrar progreso y errores claramente
  - Crear ZIP del build en `dist/AURA_Desktop_v1.0.0.zip`
- Crear `scripts/package_app.bat` que:
  - Ejecute build
  - Copie `README.md`, `docs/`, `.env.ai.example` al directorio de distribución
  - Genere `RELEASES.md` con resumen de cambios

### 6. Integración final Godot <-> Backend
- Verificar que `AuraClient` conecte correctamente al backend
- Probar flujo completo:
  1. Abrir app Godot
  2. Escribir mensaje en chat
  3. Backend responde
  4. WiFi radar muestra datos
  5. Earthquake panel muestra eventos
  6. Gestos detectados (si hay cámara)
- Corregir cualquier fallo de conexión

### 7. Documentación final de Godot
- Actualizar `docs/godot-integration.md` con:
  - Pasos exactos para abrir el proyecto en Godot 4.3
  - Comandos de build verificados
  - Troubleshooting común
  - Cómo conectar al backend
  - Cómo agregar nuevos plugins

## Reglas
- NO modifiques `docs/training/strategy.md`, `services/discord-bot/PROMPT_NEXT_AGENT*.md`
- NO subas secrets ni API keys
- Si Godot no está instalado, reporta y detente; no inventes rutas
- Usa `print()` en GDScript solo para debug
- Mantén compatibilidad 100% con el backend existente

## Entregables
1. Errores corregidos en escenas/scripts Godot (si los hay)
2. `godot/export/export_presets.cfg` actualizado con presets reales
3. Build real verificado: `build/windows/AURA Desktop.exe` (o reporte de error detallado)
4. `scripts/build_godot.bat` mejorado con detección automática de Godot
5. `scripts/package_app.bat` funcional
6. `dist/AURA_Desktop_v1.0.0.zip` empaquetado (si build exitoso)
7. `docs/godot-integration.md` actualizado

## Validación final
```bash
godot --headless --check-only --path godot
scripts/build_godot.bat windows
dir build/windows
```

Reportar: ¿compila Godot sin errores? ¿se generó el .exe? ¿qué falló si algo falló?
