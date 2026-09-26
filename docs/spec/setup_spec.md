---
title: "AURA System Architecture - Setup Specification"
description: "Especificación de la arquitectura actual de AURA y metodología de desarrollo"
author: "AURA System"
date: "2026-05-27"
tags: ["architecture", "spec", "setup", "methodology"]
---

# 📜 **AURA System Architecture - Setup Specification**
*"Especificación Primero: Todo desarrollo debe ser precedido por una entrada en el archivo de especificación correspondiente"*

---

## 🎯 **Objetivo**
Establecer la estructura actual de AURA y definir el **Protocolo de Especificación Primero** para todo desarrollo futuro.

---

## 🏗️ **Arquitectura Actual de AURA**

### 🔹 **Componentes Principales**

| Componente | Descripción | Ruta | Estado |
|------------|-------------|------|--------|
| **Main Core** | Servidor principal de AURA (FastAPI) | `AME_Core/servidor_ame.py` | ✅ Operativo |
| **Shadow-Core** | Microservicio aislado para operaciones avanzadas | `AME_Core/shadow_core.py` (Puerto 5001) | ✅ Operativo |
| **Security Shield** | Módulo de detección de amenazas | `AME_Core/security_shield.py` | ✅ Integrado |
| **Protocolo de Pánico** | Respuesta a amenazas (Dashboard + 3D) | `AME_Core/templates/blue_dashboard.html` | ✅ Implementado |
| **PHYS-UI-ENGINE** | Interfaz 3D con física realista | `AME_Core/static/js/physics_ui.js` | ✅ Verificado |
| **Integración Obsidian** | Segundo Cerebro (búsqueda de conocimientos) | `knowledge_fetcher.py` | ✅ Configurado |
| **Alternancia de IA** | Local (Ollama) vs Nube (Gemini) | `plugins/ai_router.py` | ✅ Implementado |

---

## 📂 **Estructura de Directorios**

```
AURA/
├── spec/                  # Especificaciones técnicas (Spec Kit)
│   ├── setup_spec.md      # Arquitectura y metodología
│   ├── 001-shadow-core-spec.md  # Shadow-Core
│   └── ...                 # Otras especificaciones
├── plugins/               # Módulos independientes
│   ├── ai_router.py       # Alternancia de IA
│   └── ...                 # Otros plugins
├── Shadow-Core/          # Módulos del Shadow-Core
│   ├── net_recon_ghost.py
│   └── data_exfiltration_layer.py
├── AME_Core/              # Main Core
│   ├── servidor_ame.py    # Servidor principal
│   ├── shadow_core.py     # Shadow-Core (microservicio)
│   ├── security_shield.py # Seguridad
│   └── ...
├── AURA_Core/             # Componentes adicionales
│   ├── aura_core.py       # Núcleo principal
│   └── ...
├── knowledge_fetcher.py  # Integración con Obsidian
├── physics_ui.js         # Módulo de física 3D
├── test_physics.html      # Prueba de física 3D
└── ...
```

---

## 📜 **Protocolo de Especificación Primero**

### 🔹 **Reglas Obligatorias**
1. **Todo desarrollo debe ser precedido por una especificación:**
   - Antes de modificar o añadir código, debe crearse/actualizarse un archivo `.md` en `/spec/`
   - El archivo debe describir:
     - Objetivo del cambio
     - Riesgos potenciales
     - Pasos técnicos detallados
     - Impacto en otros componentes

2. **Estructura de los archivos de especificación:**
   ```markdown
   ---
   title: "Nombre del Cambio"
   description: "Breve descripción"
   author: "AURA System"
   date: "YYYY-MM-DD"
   tags: ["componente", "tipo-de-cambio"]
   ---
   ```

3. **Flujo de trabajo:**
   ```
   1. Crear/actualizar especificación en /spec/
   2. Revisar con el equipo (si aplica)
   3. Implementar el cambio según la especificación
   4. Documentar resultados en la especificación
   ```

---

## 🛠️ **Metodología de Desarrollo**

### 🔹 **Pasos para cualquier cambio:**
1. **Consultar especificación existente:**
   - Revisar `/spec/` para ver si el cambio ya está documentado
   - Si existe una especificación pendiente, implementarla primero

2. **Crear nueva especificación (si es necesario):**
   - Archivo: `/spec/[nombre].md`
   - Contenido:
     - **Objetivo:** ¿Qué se quiere lograr?
     - **Riesgos:** ¿Qué podría salir mal?
     - **Pasos Técnicos:** ¿Cómo se implementará?
     - **Impacto:** ¿Qué otros componentes se ven afectados?

3. **Implementar el cambio:**
   - Seguir exactamente lo especificado
   - No desviarse del plan sin actualizar la especificación

4. **Documentar resultados:**
   - Actualizar la especificación con:
     - Estado final
     - Pruebas realizadas
     - Problemas encontrados y soluciones

---

## 📋 **Ejemplo de Especificación**

**Archivo:** `/spec/physics_ui_integration.md`

```markdown
---
title: "Integración de PHYS-UI-ENGINE en Dashboard"
description: "Convertir el dashboard a una interfaz 3D con física realista"
author: "AURA System"
date: "2026-05-27"
tags: ["dashboard", "3d", "physics", "integration"]
---

## 🎯 Objetivo
Integrar el módulo PHYS-UI-ENGINE en el dashboard actual para crear una interfaz 3D con física realista, inspirada en el estilo Antigravity.

## 🔧 Pasos Técnicos
1. **Añadir librerías:**
   - Three.js v0.132.2
   - Cannon-es v0.20.0
   - OrbitControls y DragControls

2. **Modificar blue_dashboard.html:**
   - Añadir canvas 3D como capa base
   - Integrar physics_ui.js

3. **Convertir elementos a objetos 3D:**
   - Terminal de Auto-Evolución → Cubo con física
   - Terminal de Telemetría → Panel flotante
   - Botones y paneles → Objetos interactivos

4. **Configurar física:**
   - Gravedad ajustada para efecto "antigravedad"
   - Efectos de resorte al arrastrar elementos
   - Colisiones y rebotes realistas

## ⚠️ Riesgos
- **Conflictos con librerías existentes:** Verificar que Three.js no interfiera con antigravity_nodes.js
- **Rendimiento:** Asegurar que la física no afecte el rendimiento del dashboard
- **Compatibilidad:** Elementos HTML existentes deben adaptarse al nuevo sistema 3D

## 📌 Estado Actual
✅ Librerías integradas en blue_dashboard.html
✅ Módulo physics_ui.js creado y verificado
✅ Prueba exitosa con cubo 3D interactivo
```

---

## 🔄 **Proceso de Revisión**

### 🔹 **Antes de implementar cualquier cambio:**
1. **Pregunta obligatoria:**
   *"¿Debo actualizar el archivo de especificación antes de proceder?"*

2. **Respuesta esperada:**
   - Si el cambio no está especificado: **"Sí, crea/actualiza la especificación primero"**
   - Si el cambio está especificado: **"Procede según la especificación existente"**

---

## 📅 **Historial de Cambios**

| Fecha | Cambio | Especificación | Estado |
|-------|--------|----------------|--------|
| 2026-05-27 | Integración PHYS-UI-ENGINE | `/spec/physics_ui_integration.md` | ✅ Implementado |
| 2026-05-27 | Alternancia de IA | `/spec/ai_router_spec.md` | ✅ Implementado |
| 2026-05-27 | Integración Obsidian | `/spec/obsidian_integration.md` | ✅ Implementado |
| 2026-05-27 | Shadow-Core | `/spec/001-shadow-core-spec.md` | ✅ Implementado |

---

## 📌 **Notas Finales**

- **Este protocolo es obligatorio:** Todo desarrollo sin especificación previa será rechazado
- **Las especificaciones son la verdad única:** El código debe seguir exactamente lo especificado
- **Documentación es código:** Las especificaciones son tan importantes como el código mismo

---
**Última actualización:** 27/05/2026
**Estado:** Protocolo activado
**Responsable:** AURA System