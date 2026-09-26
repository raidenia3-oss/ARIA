# Especificación del Proyecto AURA

**Metodología OpenSpec (OPSX) - Alcance Global del Enjambre**

## **1. Contexto y Objetivos**

AURA es un sistema de inteligencia distribuida que integra módulos de OSINT, monitoreo de red, y alertas en tiempo real. Este documento define el alcance global del proyecto y los principios de desarrollo bajo la metodología OpenSpec.

### **1.1 Objetivos Principales**

- **Integración de módulos OSINT y RuView** para análisis de amenazas y detección de intrusiones.
- **Orquestación de comandos** en Discord y alertas por WhatsApp usando CallMeBot.
- **Protocolo de Propuesta y Auditoría** para cambios en el código base.

### **1.2 Principios de Desarrollo**

- **Todo cambio debe pasar por el flujo OPSX** (Propuesta → Revisión → Aplicación).
- **Nada se modifica directamente en el código core** sin aprobación explícita.
- **Documentación clara y detallada** para cada propuesta de cambio.

---

## **2. Estructura de OpenSpec**

La estructura de OpenSpec sigue un modelo de **Propuesta y Auditoría** para garantizar cambios controlados y documentados.

### **2.1 Estructura de Carpetas**

```
.openspec/
├── specs/
│   └── project.md          # Especificación global del proyecto
├── changes/
│   ├── active/             # Propuestas en desarrollo
│   └── archive/            # Propuestas aplicadas con éxito
```

### **2.2 Flujo de Trabajo**

1. **Crear una propuesta** en `.openspec/changes/active/` con un archivo `.md`.
2. **Revisar y aprobar** la propuesta manualmente.
3. **Aplicar los cambios** al código base.
4. **Mover la propuesta** a `.openspec/changes/archive/` una vez aplicada.

---

## **3. Reglas de Desarrollo**

### **3.1 Prohibiciones**

- **No modificar archivos core** sin pasar por el flujo OPSX.
- **No aplicar cambios sin aprobación** explícita.

### **3.2 Requisitos para Propuestas**

Cada propuesta debe incluir:

- **Contexto y objetivos** de la iteración.
- **Alternativas consideradas** (pros y contras del enfoque técnico).
- **Lista detallada de tareas** (checklist de archivos a modificar).
- **Impacto esperado** en el sistema.

---

## **4. Ejemplo de Propuesta**

Para crear una nueva propuesta, sigue el siguiente formato en `.openspec/changes/active/`:

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

---

## **5. Protocolos Adicionales**

### **5.1 Comandos de Discord**

- `/radar_on`: Activa el simulador RuView y el monitoreo de presencia.
- `/target [alias]`: Ejecuta el worker de OSINT asíncrono.
- `/swarm_status`: Muestra la telemetría del swarm (PC + Termux).

### **5.2 Alertas por WhatsApp**

- Si se detecta un evento `PHYSICAL_INTRUSION`, se envía una alerta inmediata por WhatsApp usando CallMeBot.

---

## **6. Configuración Necesaria**

### **6.1 Variables de Entorno**

- `CALLMEBOT_API_KEY`: Clave API de CallMeBot.
- `CALLMEBOT_PHONE`: Número de teléfono para alertas.
- `RUVIEW_RADAR_URL`: URL del endpoint de RuView.
- `OSINT_WORKER_URL`: URL del endpoint para OSINT.
- `TERMUX_IP_URL`: URL para obtener la IP del nodo Termux.

---

**Última actualización:** 05/06/2026
