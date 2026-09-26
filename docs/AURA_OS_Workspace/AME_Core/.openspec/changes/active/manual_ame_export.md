# OPERACIÓN: Exportación Manual del Agente AME Móvil - NÚCLEO AURA/AME (HÍBRIDO OBSIDIAN+GBRAIN)

**ID:** OPSX-AME-EXPORT-2026-06-06
**Estado:** `pending-apply`
**Autor:** Arquitecto AURA
**Prioridad:** CRÍTICA

---

## 1. Resumen Ejecutivo

Arquitectura de colmena interconectada para el ecosistema AURA/AME con integración híbrida Obsidian+GBrain. El `core/server.py` actúa como orquestador central universal sirviendo a la App Maid, la APK AME y el nodo Termux (Agent AME), mientras que GBrain proporciona indexación semántica y relacional sobre la bóveda de conocimiento.

---

## 2. Arquitectura de Interconexión

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐   │
│   │                 │    │                 │    │                         │   │
│   │   Servidor      │◄───┤   Agente       │◄───┤   Aplicaciones          │   │
│   │   Central       │    │   Termux       │    │   Móviles (App Maid    │   │
│   │  (core/server.py)│    │  (ame_termux_  │    │   y APK AME)           │   │
│   │  + GBrain       │    │   node.py)     │    │                         │   │
│   │  (Orchestrator) │    │                 │    │                         │   │
│   └─────────┬────────┘    └─────────┬───────┘    └─────────────┬───────────┘   │
│             │                         │                         │             │
│             │   ┌─────────────────┐   │                         │             │
│             │   │                 │   │                         │             │
│             │   │   Módulos       │   │                         │             │
│             │   │   Tácticos      │   │                         │             │
│             │   │  (Nmap, OSINT,  │   │                         │             │
│             │   │   Keylogger)    │   │                         │             │
│             │   └─────────┬───────┘   │                         │             │
│             │             │           │                         │             │
│             │             │           │                         │             │
│             │             ▼           │                         │             │
│             │   ┌─────────────────┐   │                         │             │
│             │   │                 │   │                         │             │
│             │   │   Bóveda de     │   │                         │             │
│             │   │   Conocimiento  │   │                         │             │
│             │   │  (AURA_INTELLI- │   │                         │             │
│             │   │   GENCE_VAULT)  │   │                         │             │
│             │   │  (Obsidian +    │   │                         │             │
│             │   │   GBrain)       │   │                         │             │
│             │   └─────────┬───────┘   │                         │             │
│             │             │           │                         │             │
│             └─────────────┘           │                         │             │
│                                        │                         │             │
│                                        ▼                         │             │
│                                        [GBrain]                  │             │
│                                        (Indexación Semántica     │             │
│                                         y Grafo Relacional)      │             │
│                                        │                         │             │
│                                        └─────────────────────────┘             │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Inventario de Archivos del Paquete

### 3.1 Backend Central (core/)

| Archivo                       | Descripción                                                    |
| ----------------------------- | -------------------------------------------------------------- |
| `core/server.py`              | Orquestador central FastAPI - Proxy des-censor + sync + estado |
| `core/gbrain_orchestrator.py` | Motor de indexación semántica y relacional (GBrain + PG Lite)  |
| `core/gbrain_dream.py`        | Ciclo de sueño para mantenimiento de la base de conocimiento   |

### 3.2 Cliente Termux (TERMUX_AGENT/)

| Archivo              | Descripción                                                       |
| -------------------- | ----------------------------------------------------------------- |
| `ame_termux_node.py` | Cliente ligero que consume endpoints del servidor PC desde Termux |

### 3.3 APK Android (ANDROID_APP/)

| Archivo/Componente    | Descripción                                                      |
| --------------------- | ---------------------------------------------------------------- |
| `android/`            | Código fuente de Android (Capacitor)                             |
| `build_apk.*`         | Scripts de compilación para generar APK                          |
| `compile_*.ps1`       | Scripts de compilación para Windows                              |
| `package.json`        | Configuración del proyecto                                       |
| `capacitor.config.ts` | Configuración de Capacitor para conectar con el servidor central |

### 3.4 Bóveda de Conocimiento (AURA_INTELLIGENCE_VAULT/)

| Carpeta/Archivo        | Descripción                                                         |
| ---------------------- | ------------------------------------------------------------------- |
| `01_Arquitectura/`     | Documentación de la arquitectura de la colmena AURA/AME             |
| `02_Configuracion/`    | Manuales de configuración para API Keys, IP local y Termux          |
| `03_Modulos_Tacticos/` | Documentación detallada de los módulos tácticos (Nmap, OSINT, etc.) |
| `04_Memory_Index/`     | Índices semánticos y grafos relacionales generados por GBrain       |
| `README.md`            | Guía de uso de la bóveda de conocimiento híbrida                    |

### 3.5 Scripts de Integración

| Archivo               | Descripción                                                       |
| --------------------- | ----------------------------------------------------------------- |
| `integrate_gbrain.py` | Script de integración entre Obsidian y GBrain                     |
| `sync_knowledge.py`   | Script para sincronizar cambios entre la bóveda y el motor GBrain |
| `gbrain_utils.py`     | Utilidades para manejo de bases de datos GBrain                   |

---

## 4. Estructura del Paquete Final

```
AME_EXPORT_PACKAGE/
├── TERMUX_AGENT/
│   ├── core/
│   │   ├── server.py
│   │   ├── gbrain_orchestrator.py
│   │   └── gbrain_dream.py
│   ├── ame_termux_node.py
│   ├── modules/
│   │   ├── osint_username.py
│   │   ├── osint_reputation.py
│   │   └── wifi_client_telemetry.py
│   ├── hooks/
│   │   └── termux_hooks.sh
│   ├── config/
│   │   ├── ame_config_template.json
│   │   └── gbrain_config.json
│   ├── install_ame.sh
│   ├── .env.example
│   └── README.md
│
├── ANDROID_APP/
│   ├── android/
│   │   ├── app/
│   │   ├── build.gradle
│   │   ├── settings.gradle
│   │   └── local.properties
│   ├── build_apk.bat
│   ├── build_apk.sh
│   ├── compile_*.ps1
│   ├── package.json
│   ├── capacitor.config.ts
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── BUILD_MOBILE.md
│
├── AURA_INTELLIGENCE_VAULT/
│   ├── 01_Arquitectura/
│   │   ├── 01_Arquitectura_General.md
│   │   ├── 02_Proxy_FastAPI.md
│   │   ├── 03_Nodo_Termux.md
│   │   └── 04_Apps_Móviles.md
│   ├── 02_Configuracion/
│   │   ├── 01_API_Keys_OpenRouter.md
│   │   ├── 02_IP_Local_Celular.md
│   │   └── 03_Instalacion_Termux.md
│   ├── 03_Modulos_Tacticos/
│   │   ├── 01_Nmap_Advanced.md
│   │   ├── 02_OSINT_Sherlock.md
│   │   └── 03_Keylogger_Táctico.md
│   ├── 04_Memory_Index/
│   │   ├── vectors.db          # Base de datos de vectores semánticos
│   │   ├── graph.db            # Base de datos del grafo relacional
│   │   ├── index.json          # Índice de archivos procesados
│   │   └── metadata.json       # Metadatos del conocimiento
│   └── README.md
│
├── scripts/
│   ├── integrate_gbrain.py
│   ├── sync_knowledge.py
│   └── gbrain_utils.py
│
├── MANIFEST.txt
└── README.md
```

---

## 5. Instrucciones de Conexión Unificadas

Al iniciar `server.py`, se imprime:

```
════════════════════════════════════════════════════════════════════════════════════════════════════
```
