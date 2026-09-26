# AURA OS v2.0 — User Guide

Bienvenido a AURA, tu asistente personal de IA.

Esta guía te enseña cómo usar todas las features de AURA OS, sin necesidad de conocimientos técnicos.

**Tabla de contenidos:**
1. [Primeros Pasos](#primeros-pasos)
2. [Interfaz Principal](#interfaz-principal)
3. [Chat Conversacional](#chat-conversacional)
4. [Voice (Voz)](#voice-voz)
5. [Skills (Habilidades)](#skills-habilidades)
6. [Automation (Automatizaciones)](#automation-automatizaciones)
7. [Plugins](#plugins)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)

---

## Primeros Pasos

### Abrir AURA

**Windows:**
1. Haz doble clic en **AURA OS** en el escritorio
2. Se abrirá automáticamente en una ventana
3. Listo — no necesitas conexión internet, todo funciona localmente

**Linux/macOS:**
```bash
python backend/main.py
# Abre navegador: http://localhost:8000
```

### Primera vez

La primera vez que abras AURA, te mostrará:

- Un **orb animado** en el centro de la pantalla
- Un panel de **habilidades** (16 iconos)
- Un **log de eventos** en la parte inferior

> **Consejo:** AURA entiende español e inglés. Escribe o habla naturalmente.

---

## Interfaz Principal

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  AURA OS v2.0  |  Backend: online  CPU: 21.4%  RAM: 58.7%  🌙   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                       [ORB ANIMADO]                             │
│                                                                 │
│                 Escribe tu mensaje aquí...                      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ HABILIDADES              │  EVENTOS                             │
│ ┌─────────┬─────────┐    │  [09:15:21 p.m.] Skill completado   │
│ │ Estado  │  Hora   │    │  [09:15:18 p.m.] Ejecutando skill   │
│ ├─────────┼─────────┤    │  [09:15:10 p.m.] Chat recibido      │
│ │ Ping    │Escanear │    │                                      │
│ └─────────┴─────────┘    │  MÉTRICAS                            │
│                           │  CPU: 21.4%  ▓▓░░░░░░░░           │
│                           │  RAM: 58.7%  ▓▓▓▓▓▓░░░░           │
│                           │  Disk: 75.2% ▓▓▓▓▓▓▓▓░░           │
└─────────────────────────────────────────────────────────────────┘
```

### Elementos

| Elemento | Función |
|----------|---------|
| **Orb animado** | Indica que AURA está activo. Cambia de color según el estado |
| **Input de chat** | Escribe tu mensaje aquí y presiona Enter |
| **Botón micrófono** | Haz clic para hablar en lugar de escribir |
| **Grid de habilidades** | Haz clic en cualquier skill para usarla directamente |
| **Log de eventos** | Historia de acciones que ejecutó AURA |
| **Métricas** | Estado del sistema en tiempo real (CPU, RAM, Disco) |
| **Modo oscuro** | Botón 🌙 en la barra superior para cambiar tema |

---

## Chat Conversacional

### Cómo charlar con AURA

Simplemente escribe como hablarías con un amigo:

> **Usuario:**  
> "¿Qué hora es?"

> **AURA:**  
> "Son las 3:45 p.m. del viernes 31 de agosto."

### Puedes pedirle:

- **Información del sistema:** "¿Qué uso tiene mi disco?"
- **Abrir aplicaciones:** "Abre Chrome" / "Abre VS Code"
- **Red:** "¿Cuál es mi IP?" / "Escanee mi red local"
- **Clima:** "¿Hace frío hoy?"
- **Recordatorios:** "Recordarme comprar leche a las 6"
- **Web:** "¿Cuál es la noticia del día?"

### Chat con contexto

AURA recuerda la conversación en la misma sesión:

> **Usuario:** "¿Quién ganó la Copa Mundial?"  
> **AURA:** "Argentina en 2022."  
> **Usuario:** "¿Y Messi cuántos goles hizo?"  
> **AURA:** "Messi marcó 7 goles en esa Copa."

### Escribir `/help` para ver comandos

Escribe `/help` en el chat para ver todos los comandos disponibles.

---

## Voice (Voz)

### HABLAR con AURA

Haz clic en el **botón micrófono** en la esquina inferior derecha, o simplemente di:

> "Hey AURA" (palabra de activación)

Y luego habla tu comando:

> "¿Cuál es mi dirección IP?"

AURA te responderá en voz (TTS) y en texto.

### Configurar voz

1. Haz clic en **⚙️ Settings** (esquina superior derecha)
2. Selecciona **Voice**
3. Cambia:
   - **Voz:** Elvira (femenina), Elena (latina), Aria (inglés)
   - **Velocidad:** Normal / Rápido / Lento
   - **Tono:** Formal / Casero / Técnico

### Offline Voice

- **STT:** Vosk funciona sin internet
- **TTS:** pyttsx3 funciona sin internet
- **Wake Word:** openWakeWord detecta "Hey AURA" offline

> Para usar voice offline, ve a Settings → Voice → Engine = Offline

---

## Skills (Habilidades)

### ¿Qué son?

Los **skills** son funciones que AURA puede ejecutar. Hay **16 skills** organizados en categorías:

### Categorías de Skills

| Categoría | Skills |
|-----------|--------|
| **System** | Estado, Hora, Ping, Escanear, WHOIS, Lock, Apps, Volume, Screenshot, Memory |
| **Web** | Search, Clima |
| **Files** | Listar, Leer, Escribir |

### Usar un skill

**Opción 1:** Haz clic directamente en el icono del skill en el grid.

**Opción 2:** Pídele a AURA:
> "¿Estado del sistema?" → ejecuta el skill **status**

**Opción 3:** Usa la API directamente:
```bash
curl -X POST http://localhost:8000/api/skills/status
curl -X POST http://localhost:8000/api/skills/ping \
  -H "Content-Type: application/json" \
  -d '{"host": "8.8.8.8"}'
```

### Skills disponibles

| Skill | Qué hace | Ejemplo |
|-------|----------|---------|
| **status** | CPU, RAM, disco, estado del backend | "¿Cómo va el sistema?" |
| **time** | Hora y fecha actuales | "¿Qué hora es?" |
| **ping** | Ping a un host | "Haz ping a google.com" |
| **scan** | Escanea puertos abiertos | "¿Puertos abiertos?" |
| **whois** | Info de dominio | "¿Quién es google.com?" |
| **open** | Abrir aplicaciones | "Abre Chrome" |
| **volume** | Control de volumen | "Baja el volumen" |
| **screenshot** | Capturar pantalla | "Captura de pantalla" |
| **memory** | Buscar en memoria | "¿Qué recordaste?" |
| **lock** | Bloquear pantalla | "Bloquea la pantalla" |
| **apps** | Listar procesos | "¿Qué apps corren?" |
| **search** | Búsqueda web | "¿Quién ganó?" |
| **weather** | Clima | "¿Hace frío?" |

---

## Automation (Automatizaciones)

### ¿Qué es?

Las **automatizaciones** te permiten crear reglas que AURA ejecuta automáticamente sin que tengas que pedírselo.

Una regla tiene:
- **Trigger:** qué la activa (hora, evento, condición)
- **Acciones:** qué hace (enviar chat, ejecutar skill, notificación)

### Tipos de Triggers

| Tipo | Cuándo se activa |
|------|-----------------|
| `on_time` | A una hora específica (ej: las 9:00 AM) |
| `on_event` | Cuando ocurre un evento (ej: recibir un chat) |
| `on_condition` | Cuando se cumple una condición (ej: CPU > 80%) |
| `on_startup` | Al iniciar AURA |

### Crear tu primera regla

**Ejemplo: Recordatorio matutino**

```bash
curl -X POST http://localhost:8000/api/automation/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Briefing matutino",
    "description": "Me avisa la hora y el clima cada mañana",
    "trigger": {
      "type": "on_time",
      "hour": 9,
      "minute": 0,
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
    },
    "actions": [
      {"type": "chat", "message": "Buenos días. Hoy es día laboral."},
      {"type": "skill", "skill": "weather"}
    ],
    "tags": ["morning", "routine"]
  }'
```

### Gestionar reglas

```bash
# Listar todas las reglas
curl http://localhost:8000/api/automation/rules

# Ejecutar una regla manualmente (para probar)
curl -X POST http://localhost:8000/api/automation/test/{rule_id}

# Habilitar/deshabilitar
curl -X PATCH http://localhost:8000/api/automation/rules/{rule_id}/enable \
  -H "Content-Type: application/json" \
  -d 'true'

# Ver estado del monitoreo
curl http://localhost:8000/api/automation/monitor/status
```

### Ejemplos de reglas útiles

1. **Cierre de apps al final del día:**
   - Trigger: on_time, 19:00
   - Acción: skill (apps) → cerrar apps no necesarias

2. **Alerta de CPU alta:**
   - Trigger: on_condition, "cpu > 80"
   - Acción: notification + skill (status)

3. **Backup semanal:**
   - Trigger: on_time, domingo 2:00 AM
   - Acción: api_call → POST a tu script de backup

---

## Plugins

### ¿Qué son?

Los **plugins** son extensiones que añaden funcionalidad a AURA. Los plugins usan **hooks** — puntos de entrada que se ejecutan en momentos específicos.

### Hooks disponibles

| Hook | Cuándo se ejecuta |
|------|-------------------|
| `on_startup` | Al iniciar AURA |
| `on_chat` | Al recibir un mensaje de chat |
| `on_skill_execute` | Al ejecutar un skill |
| `on_shutdown` | Al apagar AURA |

### Plugins incluidos

- **Example Plugin** — Plugin de demostración que muestra todos los hooks

### Crear tu propio plugin

1. Crea un archivo en `backend/plugins/custom/`:

```python
# backend/plugins/custom/mi_recordatorio.py

from datetime import datetime

class Plugin:
    name = "Mis Recordatorios"
    version = "1.0.0"

    def on_load(self):
        print("Plugin de recordatorios cargado")

    def get_hooks(self):
        return {"on_chat": self.on_chat}

    def on_chat(self, message, metadata=None):
        # Procesar cada mensaje
        if "recordar" in message.lower():
            return {"action": "saved_reminder"}
        return None
```

2. Recarga los plugins:
```bash
curl -X POST http://localhost:8000/api/plugins/reload
```

3. ¡Listo! Tu plugin está activo.

### Gestionar plugins

```bash
# Listar plugins
curl http://localhost:8000/api/plugins

# Recargar (después de crear uno nuevo)
curl -X POST http://localhost:8000/api/plugins/reload

# Descargar un plugin
curl -X DELETE http://localhost:8000/api/plugins/example_plugin
```

---

## Troubleshooting

### AURA no se abre

1. **El .exe no inicia:**
   - Verifica que Windows no esté bloqueando el archivo (SmartScreen)
   - Haz clic derecho → Propiedades → "Desbloquear"
   - Asegúrate de tener Windows 10/11 actualizado

2. **La ventana se cierra inmediatamente:**
   - Ejecuta desde PowerShell: `.\aura-os\scripts\start-aura-app.ps1 -Start`
   - Revisa la consola para errores

### AURA no responde

1. **Verifica el backend:**
   ```powershell
   .\aura-os\scripts\start-aura-app.ps1 -Status
   ```

2. **Reinicia:**
   ```powershell
   .\aura-os\scripts\start-aura-app.ps1 -Stop
   .\aura-os\scripts\start-aura-app.ps1 -Start
   ```

### El micrófono no funciona

1. Ve a Settings → Voice
2. Verifica que tu micrófono aparezca en la lista
3. Prueba con otro micrófono
4. Si usas Voice offline, instala `vosk` y descarga el modelo:
   ```powershell
   .venv\Scripts\pip install vosk sounddevice
   ```

### Los skills no funcionan

1. Verifica que estén cargados:
   ```bash
   curl http://localhost:8000/api/skills
   ```
   Debes ver 16 skills.

2. Si ves 0 skills, reinicia el backend:
   ```powershell
   .\aura-os\scripts\start-aura-app.ps1 -Stop
   .\aura-os\scripts\start-aura-app.ps1 -Start
   ```

### Problemas de audio TTS

1. Si la voz suena distorsionada, prueba otra voz:
   - Settings → Voice → Voice = Elena o Aria

2. Si no hay audio, verifica el volumen del sistema

### La interfaz se ve lenta

1. Cierra otras aplicaciones para liberar RAM/CPU
2. Desactiva animaciones en Settings → Interface → Reduce motion
3. El orb consume ~5% CPU en idle

---

## FAQ

### Pregunta: ¿Necesito internet para usar AURA?
**Respuesta:** No. AURA funciona 100% localmente. El voice offline (Vosk + pyttsx3) y el modelo de IA local (Ollama) no requieren conexión.

### Pregunta: ¿AURA guarda mis datos en la nube?
**Respuesta:** No. Todo se guarda localmente en tu disco duro (`data/` y `memory/`). No hay tracking ni telemetría.

### Pregunta: ¿Puedo usar mi propio modelo de IA?
**Respuesta:** Sí. Configura `AI_PROVIDER=local` y apunta a tu modelo de Ollama:
```bash
set AI_PROVIDER=local
set LOCAL_LFM_BASE_URL=http://localhost:11434
set LOCAL_LFM_MODEL=llama3
```

### Pregunta: ¿Cómo añado un nuevo skill?
**Respuesta:** Edita `backend/skills/system/` y crea un nuevo archivo:
```python
def run(params):
    return {"status": "ok", "result": {"mi_dato": 42}}
```
Luego registra el skill en `backend/skills/registry.py`.

### Pregunta: ¿Puedo integrar AURA con Discord?
**Respuesta:** Sí. Ve a `packages/discord-bot/` y configura tu token en `.env`.

### Pregunta: ¿Cómo hago backup de mis configuraciones?
**Respuesta:** Copia estas carpetas:
- `data/` — reglas de automatización
- `memory/` — memoria de conversaciones
- `kilo_prompts/` — tareas delegadas a Kilo

### Pregunta: ¿AURA funciona en Linux?
**Respuesta:** Sí. Ejecuta `python backend/main.py` y abre `http://localhost:8000`. El .exe es solo para Windows.

### Pregunta: ¿Cuánto espacio ocupa AURA?
**Respuesta:** El .exe standalone ocupa ~155MB. Con dependencias de desarrollo (venv), alrededor de 2GB (incluyendo modelos de voz y STT).

### Pregunta: ¿Puedo cambiar la apariencia visual?
**Respuesta:** Sí. Edita `AURA_APP/frontend/index.html` o `frontend/index.html`. La interfaz usa CSS Glassmorphic con variables de color personalizables.

---

*¿Tienes más preguntas? Abre un [issue](https://github.com/tu-usuario/AURA/issues) o visita nuestra [documentación](./API.md).*
