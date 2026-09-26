# Flujo de la Colmena AURA/AME

Este documento describe el **flujo de la colmena AURA/AME**, que representa la arquitectura interconectada del ecosistema y cómo los diferentes componentes interactúan entre sí para formar un sistema integrado de auditoría y gestión táctica.

## 🌐 Vista General del Flujo

El ecosistema AURA/AME está diseñado como una **colmena interconectada**, donde cada componente (nodo) cumple un rol específico y se comunica con los demás para formar un sistema unificado.

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐   │
│   │                 │    │                 │    │                         │   │
│   │   Servidor      │◄───┤   Agente       │◄───┤   Aplicaciones          │   │
│   │   Central       │    │   Termux       │    │   Móviles (App Maid    │   │
│   │  (core/server.py)│    │  (ame_termux_  │    │   y APK AME)           │   │
│   │                 │    │   node.py)     │    │                         │   │
│   └─────────┬────────┘    └─────────┬───────┘    └─────────────┬───────────┘   │
│             │                         │                         │             │
│             ▼                         ▼                         ▼             │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                                                                 │   │
│   │   ┌─────────────────┐    ┌─────────────────┐    ┌───────────────┐   │
│   │   │                 │    │                 │    │               │   │
│   │   │   Módulos       │    │   Bóveda de     │    │   Interfaces   │   │
│   │   │   Tácticos      │    │   Conocimiento  │    │   de Usuario  │   │
│   │   │  (Nmap, OSINT,  │    │  (Obsidian)     │    │  (Dashboards) │   │
│   │   │   Keylogger)    │    │                 │    │               │   │
│   │   └─────────┬───────┘    └─────────┬───────┘    └───────┬───────┘   │
│   │             │                         │                         │   │
│   │             └───────────────────────┘                         │   │
│   │                                                      ▲       │   │
│   │                                                      │       │   │
│   │                                                      │       │   │
│   │                                                      ▼       │   │
│   │   ┌───────────────────────────────────────────────────┐       │   │
│   │   │                                                     │       │   │
│   │   │   Servidor Central (Buffer, Procesamiento,      │       │   │
│   │   │   y Sincronización)                                │       │   │
│   │   │                                                     │       │   │
│   │   └───────────────────────────────────────────────────┘       │   │
│   │                                                                 │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Flujo de Datos y Comunicación

### 1. Conexión Inicial

1. **Agente de Termux**:
   - Se inicia y establece conexión con el servidor central.
   - Configura la sincronización bidireccional.

2. **Aplicaciones Móviles**:
   - Se conectan al servidor central mediante Capacitor.
   - Configuran la URL del servidor en `capacitor.config.ts`.

### 2. Sincronización de Datos

1. **Agente de Termux → Servidor Central**:
   - Envía datos de telemetría y eventos mediante `POST /v1/agent/sync`.
   - Recibe comandos y actualizaciones del servidor.

2. **Servidor Central → Aplicaciones Móviles**:
   - Procesa los datos recibidos del agente de Termux.
   - Almacena los datos en el buffer de memoria.
   - Proporciona endpoints para consultar el estado del agente.

### 3. Interacción con Modelos de Lenguaje

1. **Aplicaciones Móviles → Servidor Central**:
   - Envían solicitudes a `POST /v1/chat/completions`.
   - Reciben respuestas de los modelos de lenguaje disponibles.

2. **Servidor Central → Modelos de Lenguaje**:
   - Redirige las solicitudes a los modelos configurados (Llama-3, Mistral, etc.).
   - Aplica el system prompt y output cleaner configurados.

### 4. Ejecución de Módulos Tácticos

1. **Agente de Termux**:
   - Ejecuta módulos tácticos (Nmap, OSINT, Keylogger) localmente.
   - Envía los resultados al servidor central para procesamiento.

2. **Servidor Central**:
   - Recibe los resultados de los módulos tácticos.
   - Almacena los datos en el buffer para análisis posterior.
   - Proporciona endpoints para consultar los resultados.

### 5. Visualización y Análisis

1. **Aplicaciones Móviles**:
   - Consultan los datos almacenados en el servidor central.
   - Visualizan los resultados en dashboards tácticos.
   - Ejecutan análisis con modelos de lenguaje.

2. **Bóveda de Conocimiento (Obsidian)**:
   - Centraliza toda la documentación del ecosistema.
   - Permite gestión visual del flujo de la colmena mediante el grafo de conexiones.

## 📌 Componentes Clave y sus Funciones

### 1. Servidor Central (`core/server.py`)

- **Funciones principales**:
  - Orquestador central de todos los componentes.
  - Proxy compatible con OpenAI para modelos de lenguaje.
  - Punto de sincronización para agentes y aplicaciones móviles.
  - Buffer en memoria para almacenamiento temporal de datos.
  - System prompt injector y output cleaner para modelos de lenguaje.

- **Endpoints principales**:
  - `POST /v1/chat/completions`: Proxy para modelos de lenguaje.
  - `POST /v1/agent/sync`: Sincronización con el agente de Termux.
  - `GET /v1/agent/status`: Consulta de estado del agente.
  - `GET /v1/models`: Lista de modelos disponibles.
  - `GET /health`: Verificación de estado del servidor.

### 2. Agente de Termux (`ame_termux_node.py`)

- **Funciones principales**:
  - Cliente ligero para consumir endpoints del servidor central.
  - Ejecución de módulos tácticos (Nmap, OSINT, Keylogger).
  - Sincronización bidireccional de datos con el servidor central.
  - Integración con herramientas nativas de Termux.

- **Módulos tácticos integrados**:
  - Nmap Avanzado: Escaneo de redes y hosts.
  - OSINT/Sherlock: Búsqueda de inteligencia de fuentes abiertas.
  - Keylogger Táctico: Registro de pulsaciones de teclado (con consentimiento).

### 3. Aplicaciones Móviles (App Maid y APK AME)

- **Funciones principales**:
  - Interfaz de usuario para interactuar con el ecosistema.
  - Consumo de modelos de lenguaje mediante el proxy del servidor central.
  - Visualización de datos y dashboards tácticos.
  - Configuración y monitoreo de agentes y módulos.

- **Características**:
  - App Maid: Interfaz minimalista para interacción con modelos.
  - APK AME: Interfaz avanzada con dashboards tácticos y gestión de módulos.

### 4. Bóveda de Conocimiento (Obsidian)

- **Funciones principales**:
  - Centralización de toda la documentación del ecosistema.
  - Gestión visual del flujo de la colmena mediante grafo de conexiones.
  - Documentación estructurada de arquitectura, configuración y módulos tácticos.

- **Estructura**:
  - `01_Arquitectura/`: Documentación de la arquitectura del ecosistema.
  - `02_Configuracion/`: Manuales de configuración para API Keys, IP local y Termux.
  - `03_Módulos_Tácticos/`: Documentación detallada de los módulos tácticos.
  - `04_Canvas/`: Diagramas y flujos del ecosistema.

## 🔗 Flujo de Datos Detallado

### 1. Flujo de Datos del Agente de Termux

```
[Agente de Termux] → (Módulos Tácticos) → [Datos Crudos] → [Servidor Central] → (Procesamiento) → [Buffer]
                                                                                     ↓
                                                                              [Aplicaciones Móviles] → (Visualización/Análisis)
```

### 2. Flujo de Interacción con Modelos

```
[Aplicación Móvil] → (Solicitud) → [Servidor Central] → (Proxy) → [Modelo de Lenguaje] → (Respuesta) → [Servidor Central] → [Aplicación Móvil]
```

### 3. Flujo de Sincronización Bidireccional

```
[Agente de Termux] ↔ (Sincronización) ↔ [Servidor Central] ↔ (Consulta) ↔ [Aplicación Móvil]
```

## 📊 Visualización del Flujo

### 1. Diagrama de Flujo de la Colmena

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                                                               │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐   │
│   │                 │    │                 │    │                         │   │
│   │   Servidor      │◄───┤   Agente       │◄───┤   Aplicaciones          │   │
│   │   Central       │    │   Termux       │    │   Móviles               │   │
│   │  (core/server.py)│    │  (ame_termux_  │    │   (App Maid y APK AME)  │   │
│   │                 │    │   node.py)     │    │                         │   │
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
│             │   │  (Obsidian)     │   │                         │             │
│             │   └─────────┬───────┘   │                         │             │
│             │             │           │                         │             │
│             └─────────────┘           │                         │             │
│                                        │                         │             │
│                                        ▼                         │             │
│                                        [Buffer y Procesamiento]   │             │
│                                        en el Servidor Central      │             │
│                                        │                         │             │
│                                        └─────────────────────────┘             │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 2. Flujo de Datos en Tiempo Real

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────────────┐
│                 │       │                 │       │                         │
│   Agente de     │──────▶│   Servidor      │──────▶│   Aplicaciones          │
│   Termux        │       │   Central       │       │   Móviles               │
│                 │◀──────│                 │◀──────│                         │
└─────────┬────────┘       └─────────┬───────┘       └─────────────┬───────────┘
          │                         │                         │
          │   ┌─────────────────┐   │                         │
          │   │                 │   │                         │
          │   │   Módulos       │   │                         │
          │   │   Tácticos      │   │                         │
          │   │  (Nmap, OSINT,  │   │                         │
          │   │   Keylogger)    │   │                         │
          │   └─────────┬───────┘   │                         │
          │             │           │                         │
          │             │           │                         │
          │             ▼           │                         │
          │   ┌─────────────────┐   │                         │
          │   │                 │   │                         │
          │   │   Bóveda de     │   │                         │
          │   │   Conocimiento  │   │                         │
          │   │  (Obsidian)     │   │                         │
          │   └─────────────────┘   │                         │
          │                         │                         │
          └─────────────────────────┘                         │
                                    │                         │
                                    ▼                         │
                            ┌─────────────────────────┐       │
                            │                         │       │
                            │   Buffer y             │       │
                            │   Procesamiento         │       │
                            │   en el Servidor       │       │
                            │   Central               │       │
                            │                         │       │
                            └─────────────────────────┘       │
                                                      │
                                                      ▼
                                              ┌─────────────────┐
                                              │                 │
                                              │   Interfaz de    │
                                              │   Usuario       │
                                              │   (Dashboards)   │
                                              │                 │
                                              └─────────────────┘
```

## 🔗 Enlaces Relacionados

- [[01_Arquitectura/01_Arquitectura_General]]
- [[01_Arquitectura/02_Proxy_FastAPI]]
- [[01_Arquitectura/03_Nodo_Termux]]
- [[01_Arquitectura/04_Apps_Móviles]]
- [[02_Configuracion/01_API_Keys_OpenRouter]]
- [[02_Configuracion/02_IP_Local_Celular]]
- [[02_Configuracion/03_Instalacion_Termux]]
- [[03_Módulos_Tácticos/01_Nmap_Advanced]]
- [[03_Módulos_Tácticos/02_OSINT_Sherlock]]
- [[03_Módulos_Tácticos/03_Keylogger_Táctico]]

## 📌 Notas Importantes

- **Interoperabilidad**: Todos los componentes del ecosistema están diseñados para interactuar entre sí de manera fluida.
- **Seguridad**: La comunicación entre componentes está protegida y solo accesible desde dispositivos autorizados.
- **Escalabilidad**: El diseño modular permite agregar nuevos componentes y funcionalidades sin afectar el flujo existente.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Documentación**: Este documento forma parte de la bóveda de conocimiento y debe mantenerse actualizado con los cambios en el ecosistema.

## 📝 Ejemplo de Flujo de Trabajo Completo

1. **Configuración Inicial**:
   - Configura el servidor central con las API keys y modelos de lenguaje.
   - Instala y configura el agente de Termux en el dispositivo móvil.
   - Configura las aplicaciones móviles con la IP local del servidor central.

2. **Conexión y Sincronización**:
   - El agente de Termux se conecta al servidor central y establece sincronización bidireccional.
   - Las aplicaciones móviles se conectan al servidor central y configuran sus preferencias.

3. **Ejecución de Módulos Tácticos**:
   - Desde el agente de Termux, ejecuta un escaneo de red con Nmap Avanzado.
   - Los resultados se envían al servidor central y se almacenan en el buffer.
   - Desde la aplicación móvil, consulta los resultados del escaneo y visualízalos en el dashboard táctico.

4. **Interacción con Modelos de Lenguaje**:
   - Usa la aplicación móvil para enviar una consulta a un modelo de lenguaje mediante el proxy del servidor central.
   - Recibe la respuesta del modelo y analízala con herramientas de visualización.

5. **Análisis y Documentación**:
   - Exporta los resultados de los módulos tácticos y las interacciones con modelos a la bóveda de conocimiento.
   - Actualiza la documentación en Obsidian para reflejar los nuevos hallazgos y configuraciones.

6. **Monitoreo y Mantenimiento**:
   - Monitorea el estado del ecosistema mediante los dashboards de las aplicaciones móviles.
   - Realiza mantenimiento periódico de la configuración y actualiza los componentes según sea necesario.

## 📌 Solución de Problemas en el Flujo

### 1. Problemas de Conexión

- **Agente de Termux no se conecta al servidor**:
  - Verifica que ambos dispositivos estén en la misma red.
  - Asegúrate de que la IP local del servidor sea correcta.
  - Verifica que el servidor central esté en ejecución y escuchando en el puerto correcto.

### 2. Sincronización Incorrecta

- **Datos no sincronizados entre componentes**:
  - Verifica la configuración de sincronización en el agente de Termux y el servidor central.
  - Asegúrate de que no haya firewalls bloqueando la comunicación.
  - Revisa los logs de sincronización para identificar errores.

### 3. Problemas con Modelos de Lenguaje

- **Modelos no responden o devuelven errores**:
  - Verifica que las API keys sean correctas y estén configuradas.
  - Asegúrate de que los modelos estén disponibles y no bloqueados.
  - Revisa la configuración del proxy en el servidor central.

### 4. Visualización Incorrecta en Aplicaciones Móviles

- **Datos no se muestran correctamente en los dashboards**:
  - Verifica que la configuración de Capacitor en las aplicaciones móviles sea correcta.
  - Asegúrate de que las aplicaciones estén conectadas al servidor central.
  - Revisa los logs de las aplicaciones para identificar errores de visualización.

## 🎨 Representación Visual del Flujo

Para una mejor comprensión del flujo de la colmena, se recomienda utilizar herramientas de diagramación como:

1. **Mermaid.js** (para diagramas de flujo en Markdown):

   ```mermaid
   graph TD
     A[Agente de Termux] -->|Datos Crudos| B[Servidor Central]
     B -->|Procesamiento| C[Buffer]
     C -->|Datos Procesados| D[Aplicaciones Móviles]
     D -->|Solicitudes| B
     B -->|Respuestas| D
     A -->|Módulos Tácticos| B
     B -->|Documentación| E[Bóveda de Conocimiento]
   ```

2. **Diagramas en Obsidian**:
   - Utiliza el plugin "Excalidraw" o "Drawio" en Obsidian para crear diagramas visuales del flujo.
   - Crea enlaces entre los documentos de la bóveda para reflejar las conexiones en el grafo.

3. **Plantillas de Flujo**:
   - Utiliza plantillas de diagramas de flujo para documentar procesos específicos dentro del ecosistema.
   - Ejemplo: Flujo de ejecución de un módulo táctico, flujo de interacción con modelos de lenguaje, etc.

## 📌 Recomendaciones para la Documentación del Flujo

1. **Actualización Regular**:
   - Mantén este documento actualizado con los cambios en el ecosistema.
   - Añade nuevos componentes y flujos a medida que se implementen.

2. **Enlaces Cruzados**:
   - Utiliza enlaces internos (`[[Archivo]]`) para conectar este documento con otros relacionados en la bóveda.
   - Ejemplo: `[[01_Arquitectura/03_Nodo_Termux]]` para detalles sobre el agente de Termux.

3. **Diagramas Actualizados**:
   - Actualiza los diagramas visuales para reflejar la arquitectura actual del ecosistema.
   - Utiliza herramientas como Mermaid.js o Drawio para mantener los diagramas sincronizados con la documentación.

4. **Casos de Uso**:
   - Documenta casos de uso específicos que demuestren cómo el flujo de la colmena se aplica en situaciones reales.
   - Ejemplo: Flujo para auditoría de seguridad, flujo para investigación OSINT, etc.

Este documento proporciona una visión integral del flujo de la colmena AURA/AME y cómo los diferentes componentes interactúan para formar un sistema unificado de auditoría y gestión táctica.
