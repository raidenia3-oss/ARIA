# Arquitectura General de la Colmena AURA/AME

Esta documentación describe la arquitectura general del ecosistema AURA/AME, diseñado como una colmena interconectada que permite la sincronización entre el servidor central, el agente de Termux y las aplicaciones móviles.

## 🌐 Arquitectura de la Colmena

```
┌──────────────────────┐
│   PC (Server Core)   │
│  core/server.py      │
│  Puerto 8000         │
│                      │
│  POST /v1/chat/...   │◄── App Maid (celular)
│  POST /v1/agent/sync │◄── Agent AME (Termux)
│  GET  /v1/agent/status│◄── APK AME, Maid, Agent
│  GET  /v1/models     │◄── Cualquier cliente
│  GET  /health        │◄── Health check
└──────────┬───────────┘
           │
    ┌──────┼──────────────┐
    │      │              │
    ▼      ▼              ▼
┌────────┐ ┌──────────┐ ┌──────────────┐
│App Maid│ │APK AME   │ │Agent Termux  │
│(Móvil) │ │(Móvil)   │ │(ame_termux_  │
│        │ │          │ │ node.py)     │
└────────┘ └──────────┘ └──────────────┘
```

## 🔗 Componentes Principales

### 1. Orquestador Central (core/server.py)

El **orquestador central** es un servidor FastAPI que actúa como proxy y punto de sincronización para todos los componentes del ecosistema.

- **Endpoints principales**:
  - `POST /v1/chat/completions`: Proxy compatible con OpenAI para las apps móviles.
  - `POST /v1/agent/sync`: Recibe reportes del agente de Termux.
  - `GET /v1/agent/status`: Consulta de estado en tiempo real.
  - `GET /v1/models`: Lista de modelos gratuitos disponibles.

- **Funcionalidades**:
  - Rotación de modelos gratuitos (Llama-3, Qwen-Coder, Mistral).
  - System prompt injector (modo developer).
  - Output cleaner (regex anti-censura).
  - Buffer en memoria con datos de portapapeles, capturas y outputs de Nmap/OSINT.

### 2. Agente de Termux (ame_termux_node.py)

El **agente de Termux** es un cliente ligero que consume los endpoints del servidor central desde un dispositivo con Termux.

- **Funcionalidades**:
  - Sincronización bidireccional de datos.
  - Consumo de endpoints del servidor central.
  - Integración con herramientas de Termux (ganchos nativos).

### 3. Apps Móviles (App Maid y APK AME)

Las **apps móviles** son interfaces para interactuar con el ecosistema AURA/AME desde dispositivos móviles.

- **App Maid**: Aplicación para Android que consume los endpoints del servidor central.
- **APK AME**: Aplicación móvil nativa que también interactúa con el servidor central.

## 🔄 Flujo de Datos

1. **Sincronización**:
   - El agente de Termux envía datos al servidor central mediante `POST /v1/agent/sync`.
   - El servidor central procesa y almacena los datos en memoria.

2. **Consulta de Estado**:
   - Las apps móviles pueden consultar el estado del agente de Termux mediante `GET /v1/agent/status`.

3. **Interacción con Modelos**:
   - Las apps móviles interactúan con modelos de lenguaje mediante `POST /v1/chat/completions`.

## 📌 Notas Importantes

- **Uso legítimo**: Esta arquitectura está diseñada para auditoría y gestión de infraestructura propia.
- **Seguridad**: Todos los endpoints están protegidos y solo accesibles desde dispositivos autorizados.
- **Enlaces relacionados**:
  - [[02_Proxy_FastAPI]]
  - [[03_Nodo_Termux]]
  - [[04_Apps_Móviles]]
