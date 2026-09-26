# AURA_CONTEXT_MANIFEST.md

# Manifiesto de Contexto para Sistema Distribuido AURA

# Versión: 1.0

# Fecha: 2026-06-05

# Autor: Sistema AURA

# Estándar: Ghost Developer Engineering Framework

---

## 📜 VISIÓN DEL SISTEMA

**Red de Enjambre Distribuida Táctica PC-Móvil**
El sistema AURA es una arquitectura de enjambre distribuido que integra nodos móviles (Termux en Android) con una estación central (PC) mediante comunicación autónoma y resiliente. El objetivo es proporcionar una plataforma táctica para telemetría, vigilancia y respuesta en entornos con conectividad intermitente.

**Objetivos Estratégicos:**

1. **Comunicación Autocurativa:** Sistemas que se autorreparan y reconfiguran ante fallos de red.
2. **Agentes Ligero:** Nodos móviles con bajo consumo de recursos (ARM64) que operan en Termux.
3. **Event-Driven Architecture (EDA):** Arquitectura dirigida por eventos centralizada en PC con agentes de campo.
4. **Resiliencia Off-Grid:** Capacidad de operar sin conexión y sincronizar datos cuando la conexión se restablece.
5. **Alertas Multicanal:** Notificaciones por Discord, WhatsApp y otros canales configurables.

---

## 📋 REQUERIMIENTOS DEL SISTEMA

### **1. Requerimientos Funcionales**

| ID      | Descripción                                                                             | Prioridad |
| ------- | --------------------------------------------------------------------------------------- | --------- |
| REQ-001 | Comunicación SSH autocurativa entre PC y nodos móviles (Termux).                        | Crítica   |
| REQ-002 | Ejecución de módulos Venice en sandbox aislada en Termux.                               | Alta      |
| REQ-003 | Bufferización local de eventos en nodos móviles cuando no hay conexión a internet.      | Alta      |
| REQ-004 | Sincronización automática de eventos bufferizados al restablecer la conexión.           | Alta      |
| REQ-005 | Integración de telemetría de radar LoRa con el EventBus central.                        | Alta      |
| REQ-006 | Alertas en tiempo real por Discord y WhatsApp para eventos críticos.                    | Media     |
| REQ-007 | Compilación automática de APKs actualizados en la PC y despliegue a nodos móviles.      | Alta      |
| REQ-008 | Monitoreo de cambios en el código fuente y sincronización automática con nodos móviles. | Alta      |

### **2. Requerimientos No Funcionales**

| ID      | Descripción                                                               | Valor Objetivo |
| ------- | ------------------------------------------------------------------------- | -------------- |
| RNF-001 | Tiempo de respuesta para eventos críticos (≤ 2 segundos).                 | ≤ 2s           |
| RNF-002 | Consumo de batería en nodos móviles (≤ 5% por hora en modo inactivo).     | ≤ 5%/hora      |
| RNF-003 | Tamaño máximo de buffer local en nodos móviles (≤ 10MB).                  | ≤ 10MB         |
| RNF-004 | Tiempo máximo de sincronización al restablecer conexión (≤ 30 segundos).  | ≤ 30s          |
| RNF-005 | Compatibilidad con Android ARM64 (Termux) sin dependencias x86.           | 100%           |
| RNF-006 | Resiliencia a fallos de red (máximo 3 intentos de reconexión automática). | 3 intentos     |

---

## 🏗️ ARQUITECTURA DEL SISTEMA

### **1. Arquitectura General**

```
┌───────────────────────────────────────────────────────────────┐
│                        AURA CORE (PC)                          │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ EventBus    │    │  Event          │    │  Supervisor     │  │
│  │ Central     │◄───┤  Processor      │◄───┤  de Nodos      │  │
│  └─────────────┘    └─────────────────┘    └─────────────────┘  │
│          ▲                  ▲                          ▲          │
│          │                  │                          │          │
│  ┌────────┴─────────┐  ┌─────┴─────────┐    ┌─────────┴───────┐  │
│  │   Alertas       │  │  Base de      │    │  Interfaz de   │  │
│  │  (Discord/WA)   │  │  Datos        │    │  Usuario        │  │
│  └─────────────────┘  │  (SQLite)      │    └───────────────┘  │
│                       └─────────────────┘                     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────────────┐
│                        NODOS MÓVILES (Termux)                │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │  Radar      │    │  Buffer         │    │  EventBus       │  │
│  │  LoRa       │───▶│  Offline        │───▶│  Local          │  │
│  │  (USB-OTG)  │    │  (SQLite)       │    │  (Python)       │  │
│  └─────────────┘    └─────────────────┘    └─────────────────┘  │
│          ▲                  ▲                          ▲          │
│          │                  │                          │          │
│  ┌────────┴─────────┐  ┌─────┴─────────┐    ┌─────────┴───────┐  │
│  │  Módulos        │  │  Sandbox      │    │  Comunicación   │  │
│  │  Venice         │  │  (Aislamiento)│    │  SSH/HTTP       │  │
│  └─────────────────┘  └─────────────────┘    └─────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### **2. Componentes Clave**

| Componente             | Descripción                                                          | Tecnología         |
| ---------------------- | -------------------------------------------------------------------- | ------------------ |
| **EventBus Central**   | Nucleo de comunicación entre nodos y PC.                             | Python, WebSockets |
| **Event Processor**    | Procesa y filtra eventos entrantes.                                  | Python             |
| **Node Supervisor**    | Monitorea y gestiona nodos móviles.                                  | Python             |
| **Buffer Offline**     | Almacena eventos localmente en nodos móviles cuando no hay conexión. | SQLite, Python     |
| **Radar LoRa Bridge**  | Interfaz entre hardware radar y sistema.                             | Python, PySerial   |
| **Alert System**       | Envía alertas por Discord y WhatsApp.                                | Python, APIs       |
| **APK Builder**        | Compila y despliega APKs actualizados.                               | Capacitor, Gradle  |
| **Hot Reload Watcher** | Detecta cambios en el código y sincroniza con nodos.                 | Python, Watchdog   |

---

## 🛠️ STACK TECNOLÓGICO

### **1. Tecnologías Principales**

| Categoría         | Tecnología                   | Versión/Detalle                      |
| ----------------- | ---------------------------- | ------------------------------------ |
| **Lenguaje**      | Python                       | 3.11+ (estándar en ambos lados)      |
| **Sistema**       | Termux (Android)             | ARM64, sin dependencias x86          |
| **Base de Datos** | SQLite                       | Local en nodos móviles y PC          |
| **Comunicación**  | SSH                          | Puerto 8022, autenticación por clave |
| **Event Bus**     | WebSockets / Sockets Locales | Comunicación bidireccional           |
| **Build**         | Capacitor + Gradle           | Para compilación de APKs             |
| **Alertas**       | Discord API / WhatsApp Web   | Notificaciones en tiempo real        |
| **Sandbox**       | Aislamiento de procesos      | Ejecución segura de módulos Venice   |

### **2. Restricciones Físicas y de Arquitectura**

| Restricción                      | Detalle                                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------ |
| **Arquitectura ARM64**           | Todos los nodos móviles operan en Android ARM64 (Termux). Prohibido instalar binarios x86. |
| **Sin Servidores Pesados**       | Prohibido instalar IDEs como VS Code o servidores x86 en nodos móviles.                    |
| **Bash Puro**                    | Uso preferente de Bash para scripts en Termux.                                             |
| **Python Estándar**              | Solo usar librerías estándar o disponibles en Termux (ej: `pyserial`, `sqlite3`).          |
| **Sin APT/PKG para Instalación** | No usar `pkg install` para instalar dependencias críticas. Usar solo Python y Bash.        |
| **Tamaño de Buffer Limitado**    | Máximo 10MB por buffer en nodos móviles.                                                   |
| **Autonomía de Batería**         | Consumo ≤ 5% por hora en modo inactivo.                                                    |

---

## 📂 ESTRUCTURA DE CARPETAS (SCAFFOLD)

```
AURA/
│
├── AURA_CORE/                  # Estación central (PC)
│   ├── event_bus/             # Núcleo de comunicación
│   ├── event_processor/       # Procesamiento de eventos
│   ├── node_supervisor/       # Monitoreo de nodos
│   ├── alerts/                # Sistema de alertas
│   ├── logs/                  # Logs de eventos
│   │   └── radar_events/      # Eventos de radar
│   ├── scripts/               # Scripts de automatización
│   │   ├── deploy_ame.ps1     # Despliegue automático
│   │   ├── hot_reload_watcher.py
│   │   └── pc_event_supervisor.py
│   └── AURA_CONTEXT_MANIFEST.md # Este archivo
│
├── AME_Core/                   # Frontend móvil (Capacitor)
│   ├── static/                # Recursos estáticos
│   ├── templates/             # Plantillas HTML
│   ├── index.html             # Página principal
│   └── ...
│
├── scripts/                    # Scripts compartidos
│   ├── ame_serial_bridge.py   # Puente serial para radar
│   ├── offline_buffer.py      # Buffer offline en Termux
│   ├── termux_radar_integration.py
│   └── integrated_radar_monitor.py
│
├── android/                    # Configuración de Android
│   └── app/                   # Código nativo de Capacitor
│
├── dist/                      # Salida de compilación
│
└── README.md                   # Documentación general
```

---

## 🔧 REGLAS DE INGENIERÍA LIMPIA

### **1. Flujo de Trabajo (8 Etapas)**

1. **Creación del Manifiesto:** Documentar visión, requisitos y arquitectura antes de escribir código.
2. **Scaffold Previo:** Verificar estructura de carpetas con `pwd` y `ls` antes de modificar archivos.
3. **Desarrollo Fragmentado:** Dividir tareas en micro-fases (A, B, C) y validar cada fase antes de avanzar.
4. **Validación Manual:** Cada fase debe ser validada manualmente en la terminal antes de continuar.
5. **Pruebas Unitarias:** Implementar pruebas básicas para cada componente crítico.
6. **Documentación Incremental:** Actualizar el manifiesto con cambios y decisiones tomadas.
7. **Integración Controlada:** Integrar componentes solo cuando estén validados individualmente.
8. **Despliegue Gradual:** Desplegar en entornos de prueba antes de producción.

### **2. Prohibiciones**

- **Prohibido:** Generar código sin validar el manifiesto y la estructura de carpetas.
- **Prohibido:** Usar comandos improvisados sin documentación previa.
- **Prohibido:** Instalar dependencias no estándar en Termux (ej: VS Code, servidores x86).
- **Prohibido:** Avanzar a la siguiente fase sin validación manual de la fase actual.

### **3. Validación de Entorno**

Antes de ejecutar cualquier script, verificar el entorno con:

```bash
# En PC (Windows)
cd C:\Users\User\Downloads\AURA
pwd
ls

# En Termux (Android)
pwd
ls
```

---

## 📅 PLAN DE DESARROLLO FRAGMENTADO

### **Fase A: Validación del Entorno y Scaffold**

1. **Validar estructura de carpetas** en PC y Termux.
2. **Crear directorios faltantes** según el scaffold definido.
3. **Verificar permisos** en archivos y directorios.
4. **Documentar desviaciones** del scaffold en el manifiesto.

### **Fase B: Comunicación Base SSH**

1. **Configurar conexión SSH** entre PC y Termux.
2. **Validar autenticación** con clave SSH.
3. **Implementar prueba de conexión** en scripts.
4. **Documentar IP y puertos** usados.

### **Fase C: Buffer Offline en Termux**

1. **Implementar buffer local** en SQLite para eventos de radar.
2. **Validar almacenamiento y recuperación** de eventos.
3. **Implementar sincronización** automática al restablecer conexión.
4. **Documentar formato de eventos** y estructura de buffer.

_(Fases posteriores serán definidas y validadas manualmente antes de su implementación)_

---

## 📝 NOTAS Y DECISIONES

1. **Comunicación SSH:**
   - Puerto: 8022 (evitar conflictos con servicios estándar).
   - Autenticación: Clave SSH (`id_rsa` en PC, `~/.ssh/` en Termux).
   - Fallback: Usar HTTP temporal si SSH no está disponible.

2. **EventBus:**
   - Centralizado en PC para evitar sobrecarga en nodos móviles.
   - Soporte para WebSockets y sockets locales en Termux.

3. **Radar LoRa:**
   - Formato de datos crudos: `TGT:ID,distance,velocity,angle,signal_strength|...`
   - Transformación a JSON estructurado en el puente serial.

4. **Alertas:**
   - Integración con APIs de Discord y WhatsApp Web.
   - Filtro de eventos críticos (ej: objetivos a distancia ≤ 50m).

5. **Despliegue:**
   - Script `deploy_ame.ps1` para compilación y sincronización automática.
   - APKs generados en `C:\Users\User\Desktop\AME_PROD.apk`.

---

## 🔒 SEGURIDAD Y RESILIENCIA

1. **Aislamiento de Módulos:**
   - Ejecución de módulos Venice en sandbox aislada en Termux.
   - Uso de `pkill` para matar procesos no respondedores.

2. **Bufferización Segura:**
   - Eventos comprimidos con `zlib` y verificados con SHA-256.
   - Límite de tamaño de buffer (10MB).

3. **Reconexión Automática:**
   - Máximo 3 intentos de reconexión SSH.
   - Tiempo de espera exponencial entre intentos (1s, 2s, 4s).

4. **Logs y Auditoria:**
   - Todos los eventos guardados en logs rotativos en PC.
   - Registros de errores en `/sdcard/aura_radar_logs/` en Termux.

---

## � MÓDULOS VENICE - WORKER DE INTELIGENCIA DIGITAL

### **Scaffold de Módulos OSINT**

```
venice_modules/
│
├── __init__.py                    # Módulo Venice OSINT
├── osint_username.py              # USERNAME SLURPER - Reconocimiento de usuarios
│   ├── check_platforms()          # Peticiones asíncronas a 15+ plataformas
│   ├── build_profile_report()     # Genera reporte JSON estructurado
│   └── format_report()            # Formatea a texto estético para Discord
│
├── osint_reputation.py            # ANALIZADOR DE REPUTACIÓN - IP/Dominio
│   ├── check_ip_reputation()      # Verifica listas negras públicas
│   ├── check_domain_reputation()  # Reputación de dominios
│   ├── analyze_headers()          # Análisis de cabeceras HTTP
│   └── format_report()            # Formatea resultados
│
├── discord_bridge.py              # INTEGRACIÓN DISCORD - CommandParser
│   ├── process_target_cmd()       # Maneja '/target [nombre]'
│   ├── process_ip_cmd()           # Maneja '/checkip [ip]'
│   └── clean_json_for_discord()   # Limpia y formatea JSON para Discord
│
└── README.md                      # Documentación de módulos
```

### **Esquema de Datos - Evento OSINT**

```json
{
  "command": "/target",
  "target": "username",
  "timestamp": "2026-06-05T20:00:00Z",
  "results": [
    {
      "platform": "github",
      "username": "username",
      "profile_url": "https://github.com/username",
      "status": "found",
      "response_code": 200
    },
    {
      "platform": "reddit",
      "username": "username",
      "status": "not_found",
      "response_code": 404
    }
  ],
  "summary": {
    "total_checked": 15,
    "found": 5,
    "not_found": 10
  }
}
```

### **Plataformas Soportadas (15 principales)**

| #   | Plataforma | URL Base                             | Método |
| --- | ---------- | ------------------------------------ | ------ |
| 1   | GitHub     | `https://github.com/{user}`          | GET    |
| 2   | Instagram  | `https://www.instagram.com/{user}/`  | GET    |
| 3   | Reddit     | `https://www.reddit.com/user/{user}` | GET    |
| 4   | Twitter/X  | `https://x.com/{user}`               | GET    |
| 5   | Discord    | `https://discord.com/users/{user}`   | GET    |
| 6   | Telegram   | `https://t.me/{user}`                | GET    |
| 7   | TikTok     | `https://www.tiktok.com/@{user}`     | GET    |
| 8   | YouTube    | `https://www.youtube.com/@{user}`    | GET    |
| 9   | Twitch     | `https://www.twitch.tv/{user}`       | GET    |
| 10  | Pinterest  | `https://www.pinterest.com/{user}/`  | GET    |
| 11  | Medium     | `https://medium.com/@{user}`         | GET    |
| 12  | Dev.to     | `https://dev.to/{user}`              | GET    |
| 13  | Keybase    | `https://keybase.io/{user}`          | GET    |
| 14  | GitLab     | `https://gitlab.com/{user}`          | GET    |
| 15  | BitBucket  | `https://bitbucket.org/{user}/`      | GET    |

### **Integración Discord: Comandos**

| Comando                 | Función                     | Descripción                      |
| ----------------------- | --------------------------- | -------------------------------- |
| `/target [username]`    | `process_target_cmd()`      | Busca username en 15 plataformas |
| `/checkip [ip]`         | `process_ip_cmd()`          | Verifica reputación de IP        |
| `/checkdomain [domain]` | `check_domain_reputation()` | Verifica reputación de dominio   |

### **Restricciones Técnicas**

- **Python 3 puro** - Sin dependencias externas (solo `requests` estándar)
- **Cross-platform** - Funciona en Windows PC y Termux ARM64
- **Timeouts agresivos** - 5 segundos máximo por petición
- **Sin scraping pesado** - Solo verificación de HTTP status codes
- **Output JSON limpio** - Listo para formatear a Discord

---

## �📅 CRONOGRAMA (Ejemplo)

| Fase              | Tarea                               | Responsable | Estado | Fecha Estimada |
| ----------------- | ----------------------------------- | ----------- | ------ | -------------- |
| A. Validación     | Validar scaffold y entorno          | Cline       | ✅     | 2026-06-05     |
| B. SSH Base       | Configurar comunicación SSH         | Cline       | 🔄     | 2026-06-06     |
| C. Buffer Offline | Implementar buffer SQLite en Termux | Cline       | 🔄     | 2026-06-07     |
| D. Radar Bridge   | Puente serial para radar LoRa       | Cline       | 🔄     | 2026-06-08     |
| E. EventBus       | Implementar EventBus centralizado   | Cline       | ❌     | -              |

---

## 📌 CONCLUSIÓN

Este manifiesto define la visión, requisitos, arquitectura y reglas para el desarrollo del sistema AURA. Todas las decisiones técnicas deben alinearse con lo documentado aquí. Antes de proceder con cualquier modificación de código, se debe:

1. Validar manualmente el entorno con `pwd` y `ls`.
2. Asegurarse de que la estructura de carpetas coincida con el scaffold definido.
3. Obtener aprobación para avanzar a la siguiente fase.

---

## 🔒 PROTOCOLO OPSX (OpenSpec)

**Metodología de Propuesta y Auditoría para Cambios Controlados**

### **1. Introducción**

A partir de ahora, **todos los cambios en el código base deben pasar por el flujo OpenSpec (OPSX)** para garantizar un desarrollo controlado, documentado y auditado.

### **2. Estructura de OpenSpec**

```
.openspec/
├── specs/
│   └── project.md          # Especificación global del proyecto
├── changes/
│   ├── active/             # Propuestas en desarrollo (requieren aprobación)
│   └── archive/            # Propuestas aplicadas con éxito
```

### **3. Flujo de Trabajo**

1. **Crear una propuesta** en `.openspec/changes/active/` con un archivo `.md`.
2. **Revisar y aprobar** la propuesta manualmente.
3. **Aplicar los cambios** al código base.
4. **Mover la propuesta** a `.openspec/changes/archive/` una vez aplicada.

### **4. Requisitos para Propuestas**

Cada propuesta debe incluir:

- **Contexto y objetivos** de la iteración.
- **Alternativas consideradas** (pros y contras del enfoque técnico).
- **Lista detallada de tareas** (checklist de archivos a modificar).
- **Impacto esperado** en el sistema.

### **5. Ejemplo de Propuesta**

```markdown
# [Título de la Propuesta]

**Autor:** [Nombre]
**Fecha:** [DD/MM/AAAA]

## **Contexto**

Descripción del problema o mejora a implementar.

## **Objetivos**

- Objetivo 1
- Objetivo 2

## **Alternativas Consideradas**

| Alternativa | Pros | Contras |
| ----------- | ---- | ------- |
| Opción 1    | ...  | ...     |
| Opción 2    | ...  | ...     |

## **Tareas**

- [ ] Modificar archivo 1
- [ ] Modificar archivo 2
- [ ] Probar funcionalidad

## **Impacto Esperado**

Descripción del impacto en el sistema.
```

### **6. Prohibiciones**

- **No modificar archivos core** sin pasar por el flujo OPSX.
- **No aplicar cambios sin aprobación** explícita.

### **7. Comandos para Gestión de Propuestas**

- **Crear propuesta:** `opsx propose` (simulado manualmente en `.openspec/changes/active/`).
- **Aplicar propuesta:** `opsx apply` (solo después de aprobación manual).
- **Archivar propuesta:** Mover el archivo de `.openspec/changes/active/` a `.openspec/changes/archive/`.

---

**Próximos Pasos:**
