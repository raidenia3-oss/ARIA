# 🔴 AURA SYSTEM — TELEMETRÍA ACTIVA
**Fecha:** 2026-05-26 — **Estado:** ONLINE ✅

---

## 🚀 Proceso PM2

| ID | Nombre              | Modo | ↺  | Estado | CPU | Memoria |
|----|---------------------|------|----|--------|-----|---------|
| 0  | AURA_SITUATION_ROOM | fork | 0  | online | 0%  | 3.9mb   |

### **Comandos Rápidos**
```bash
pm2 start AURA_SITUATION_ROOM    # Encender
pm2 stop AURA_SITUATION_ROOM     # Apagar
pm2 restart AURA_SITUATION_ROOM  # Reiniciar
pm2 logs AURA_SITUATION_ROOM     # Ver logs
pm2 save                         # Guardar persistencia
```

---

## 📡 Endpoints Operativos

| Método | Ruta                    | Descripción                | Estado |
|--------|-------------------------|----------------------------|--------|
| GET    | /                       | Dashboard principal        | ✅     |
| GET    | /blue                   | Dashboard B.L.U.E.         | ✅     |
| GET    | /api/status             | Salud del sistema          | ✅     |
| POST   | /api/chat               | AURA Cognitive Router     | ✅     |
| GET    | /api/radar              | OSINT Radar táctico       | ✅     |
| POST   | /api/stark/assimilate   | Stark Extraction Engine   | ✅     |
| GET    | /api/evolution/proposals| Evolution Engine          | ✅     |
| POST   | /api/evolution/apply    | Aplicar mejoras           | ✅     |
| POST   | /api/sensor/wifi_csi    | CSI Spectrum Scanner      | ✅     |
| POST   | /api/sensor/acoustic    | Radar acústico            | ✅     |
| POST   | /api/void/save          | VOID memory               | ✅     |
| GET    | /api/watchlist          | Watchlist                 | ✅     |
| GET    | /api/ticker             | Alertas globales          | ✅     |

---

## 🛡️ Sensores Activos

| Sensor                | Estado | Puerto | Frecuencia |
|-----------------------|--------|--------|------------|
| CSI Wi-Fi (WiFi CSI)  | ✅     | POST   | 2s polling |
| Radar Acústico        | ✅     | POST   | On demand  |
| OSINT Radar           | ✅     | GET    | 5 min auto |
| Intelrift Predictive  | ✅     | GET    | On demand  |

---

## 🔄 Componentes Autónomos

| Componente             | Archivo                        | Ciclo de Vida                   |
|------------------------|--------------------------------|---------------------------------|
| Stark Extraction       | `modulo_asimilacion.py`        | Asimila → Inspira → Propone     |
| Evolution Engine       | `evolution_core.py`            | Lee pool → Valida → Empaqueta   |
| AI Router              | `ai_router.py`                 | Enruta peticiones IA            |
| OSINT Radar            | `osint_radar.py`               | Briefings tácticos RSS          |
| VOID Memory            | `void.py`                      | Memoria persistente             |

---

## 📊 Estadísticas de Producción
- **Uptime:** Persistente 24/7 (PM2)
