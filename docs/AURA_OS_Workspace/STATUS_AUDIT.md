> **Última actualización:** 02/06/2026 13:48
> **Estado general:** <span style="color:green">🟢 OPERATIVO</span>

---

## 📊 Resumen del Sistema

| Métrica                   | Valor                                   |
| ------------------------- | --------------------------------------- |
| **Servidor Backend**      | `0.0.0.0:5000` (Flask + WebSocket)      |
| **Puerto C2 (Dashboard)** | `0.0.0.0:8000` (Flask-SocketIO)         |
| **APK**                   | `AME_Actualizacion_v1.0.2.apk` (237 MB) |
| **Java**                  | OpenJDK 21.0.11 (Temurin LTS)           |
| **Node.js**               | v26.0.0                                 |
| **Capacitor**             | 8.3.4                                   |
| **Python env**            | `(env)` activo, pip 26.1.1              |

---

## ✅ Componentes Completados

- [x] **APK compilado** con Gradle 8.14.3 + AGP 8.13.0
- [x] **Servidor Flask** con CORS global (`*`) y WebSockets
- [x] **WebSocket events:** `connect`, `disconnect`, `telemetry`, `command`
- [x] **Dashboard universal** en `AME_Core/templates/dashboard_universal.html`
- [x] **Servidor C2** (`servidor_c2.py`) en puerto 8000
- [x] **Tactical Queue** (SQLite Pub/Sub) en `Shadow-Core/tactical_queue.py`
- [x] **StealthTunnel** (Tor SOCKS5) en `Shadow-Core/Network/StealthTunnel.py`
- [x] **Endpoint OTA:** `GET /api/descargar-ame`
- [x] **Context7 v1.0.0** instalado globalmente
- [x] **VS Code extensions.json** configurado con 22 extensiones
- [x] **APK copiado al Escritorio** como `AME_Actualizacion_v1.0.2.apk`

---

## 🔄 Pendientes / Backlog

- [ ] Instalar Tor en el sistema para StealthTunnel completo
- [ ] Reactivar autenticación HTTPBasicAuth en producción
- [ ] Configurar SSL/HTTPS para conexiones seguras desde celular
- [ ] Integrar nodos de reconocimiento con Tactical Queue
- [ ] Configurar Cloudflare Tunnel permanente

---

## 🌐 Endpoints Disponibles

### Puerto 5000 (Servidor Backend)

| Método | Endpoint             | Descripción                    |
| ------ | -------------------- | ------------------------------ |
| `GET`  | `/`                  | Dashboard HTML                 |
| `GET`  | `/api/status`        | Estado del sistema (JSON)      |
| `GET`  | `/health`            | Healthcheck                    |
| `POST` | `/api/osint`         | Ejecutar OSINT                 |
| `POST` | `/api/chat`          | Chat con AURA Cognitive Router |
| `GET`  | `/api/watchlist`     | Lista de objetivos             |
| `POST` | `/api/watchlist`     | Añadir objetivo                |
| `GET`  | `/api/ticker`        | Alertas globales               |
| `GET`  | `/api/radar`         | OSINT Radar                    |
| `GET`  | `/api/descargar-ame` | Descargar APK v1.0.2           |
| `WS`   | `ws://0.0.0.0:5000`  | WebSocket en tiempo real       |

### Puerto 8000 (C2 Dashboard Universal)

| Método | Endpoint             | Descripción                          |
| ------ | -------------------- | ------------------------------------ |
| `GET`  | `/`                  | Dashboard universal responsivo       |
| `GET`  | `/api/status`        | Estado del sistema                   |
| `GET`  | `/api/services`      | Estado de servicios (Queue, Tor, WS) |
| `GET`  | `/api/descargar-ame` | Descargar APK                        |
| `WS`   | `ws://0.0.0.0:8000`  | WebSocket C2                         |

---

## 📁 Archivos Clave del Proyecto

| Archivo                                       | Función                               |
| --------------------------------------------- | ------------------------------------- |
| `AME_Core/servidor_ame.py`                    | Backend principal (Flask + WebSocket) |
| `AME_Core/servidor_c2.py`                     | C2 Dashboard (puerto 8000)            |
| `AME_Core/templates/dashboard_universal.html` | Interfaz web responsiva               |
| `Shadow-Core/tactical_queue.py`               | Cola de tareas SQLite (Honker-style)  |
| `Shadow-Core/Network/StealthTunnel.py`        | Tráfico anónimo Tor SOCKS5            |
| `Shadow-Core/scheduler.py`                    | Scheduler de tareas programadas       |
| `AME_Actualizacion_v1.0.2.apk`                | APK compilado (Escritorio)            |
| `STATUS_AUDIT.md`                             | Este archivo de auditoría             |

---

## 🔧 Para Iniciar el Sistema

```bash
cd AME_Core
python servidor_ame.py    # Backend en puerto 5000
python servidor_c2.py     # C2 Dashboard en puerto 8000
```

### Acceso desde cualquier navegador:

- **Backend:** `http://[IP_PC]:5000/`
- **C2 Dashboard:** `http://[IP_PC]:8000/`
- **OTA APK:** `http://[IP_PC]:5000/api/descargar-ame`
