# Agent guards: patrones adoptados de `tama96` y `strix`

Fecha: 2026-10-04

Dos proyectos externos aportaron patrones que AURA no tiene. Este documento
recoge qué se verificó, qué falta realmente y dónde encaja cada cosa.

Estado a 2026-10-19:

| Hueco | Estado | Gate |
|---|---|---|
| Hueco 2 — límite de tasa | **Implementado** | `tests/gates/test_tool_rate_limit.py` (9) |
| Hueco 1 — allow/deny | **Implementado para procesos** (ProcessGuard) | `tests/gates/test_process_guard.py` (21) |
| Hueco 3 — dueño único | Diseñado, sin implementar | — |
| Gate de integridad de gates | **Implementado** | `tests/gates/test_gate_integrity.py` (22) |
| Gate de sincronía de `ai_providers.py` | **Implementado** | `tests/gates/test_ai_providers_sync.py` (14) |
| Gate de no-matar al usuario | **Implementado** | `tests/gates/test_process_guard.py` (21) |

Los que quedan abiertos tocan `backend/agents/` y están sin stagear junto a otros
810 archivos del working tree, así que van uno a uno y con gate propio.

## Fuentes

| Proyecto | Licencia | Qué se toma |
|---|---|---|
| [`siegerts/tama96`](https://github.com/siegerts/tama96) | MIT | Permisos por acción con kill switch, límites de tasa, lockfile de dueño único |
| [`usestrix/strix`](https://github.com/usestrix/strix) | Apache-2.0 | Gates que leen el artefacto en vez de confiar en el exit code; salida SARIF |

Nada se copia. Se lee el diseño y se adapta al código que ya existe.

---

## 1. Lo que AURA ya tiene

Verificado en `backend/agents/tools_registry.py`:

- `DynamicToolRegistry` (línea 165) — carga herramientas desde `backend/agents/tools`
- `ToolEntry` (línea 38) con `calls: int` como contador acumulado y `last_error`
- `SkillExecutionSandbox.execute()` (línea 116) — coerción de argumentos por tipo,
  validación de requeridos, `asyncio.wait_for` con timeout, captura de excepciones,
  serialización estructurada
- `audit()` (línea 291) y `_log()` (línea 305)
- `orchestrator.py:172` despacha con `await registry.execute_tool(tool, dict(params or {}))`

O sea: el sandbox es sólido. El hueco no es la ejecución, es **la autorización**.

## 2. Hueco 1 — no hay allow/deny por herramienta — IMPLEMENTADO PARA PROCESOS

Hoy, si el orquestador despacha una herramienta registrada, se ejecuta. No
existe interruptor maestro, ni denegar una herramienta concreta, ni distinguirlas
por riesgo.

`tama96` lo resuelve con tres niveles:

- **Kill switch maestro** — habilita o deshabilita todo el acceso de agentes
- **Toggle por acción** — allow/deny individual
- **Límite por acción** — máximo de llamadas por hora

Configuración en `~/.tama96/permissions.json`, editable a mano y desde un panel de
settings.

### Implementado: ProcessGuard

El allow/deny de terminación de procesos ya existe y es la parte que mas dano
hacia. El 2026-10-19 ARIA ejecuto `taskkill /F /IM chrome.exe` para leer la base
de cookies y cerro las ~28 ventanas de Chrome que el usuario tenia abiertas.

`ARIA_APP/backend/process_guard.py` convierte esa regla en codigo:

- **Regla base**: ARIA solo termina procesos que ella misma creo. La propiedad se
  decide por arbol de procesos (`ppid`), no por nombre: un Chrome abierto por
  ARIA (Playwright) es hijo de ARIA y se puede cerrar; el Chrome del usuario no.
- **Procesos con ventana visible** se niegan siempre (`user_window`).
- **Procesos del sistema** (`explorer.exe`, `lsass.exe`, `dwm.exe`...) se niegan
  siempre (`hard_protected`).
- **Terminar por nombre esta prohibido** (`name_kill_forbidden`): `taskkill /IM`
  mata procesos que nadie eligio.
- **Los comandos de shell** se filtran en `ARIA_APP/backend/safety_filter.py`,
  que consulta al guard antes de la lista estatica: el motivo que devuelve es el
  del proceso real, no el generico.

Skills expuestas en `native_core.py`: `process_guard_status`, `process_list`
(inspeccion sin tocar nada) y `process_terminate` (solo PID explicito).

### Punto de inserción

`SkillExecutionSandbox.execute()` (línea 116), justo antes de `self._invoke()` en
la línea 133. Una comprobación que devuelva el mismo diccionario de error que ya
usa el resto del método, sin cambiar la firma ni el contrato:

```python
# propuesta, NO implementada
verdict = self.permissions.check(entry.name)
if not verdict.allowed:
    entry.last_error = verdict.reason
    entry.calls += 1
    return {
        "success": False, "tool": entry.name, "output": None,
        "error": verdict.reason, "duration_ms": 0.0,
    }
```

El contador `entry.calls` ya existe y se incrementa en cada rama de `execute()`,
así que un total acumulado sale gratis. Pero es acumulado desde el arranque, no
por ventana: para un límite real de "N llamadas por hora" hace falta un registro
de marcas de tiempo, no reutilizar `calls`.

## 3. Hueco 2 — no hay límite de tasa — IMPLEMENTADO

`entry.calls` contaba desde que arrancaba el proceso. Un agente que disparara 500
llamadas en un minuto y otro que las repartiera en una hora eran indistinguibles.

`backend/security_manager.py` tiene `RateLimiter` (línea 88) e `is_blocked()`
(línea 125), pero es por IP y para HTTP entrante, no por acción de agente.
Reutilizarlo sin adaptarlo no tiene sentido.

Implementado en `backend/agents/tools_registry.py`: ventana deslizante por
herramienta, con la inspección al principio de `execute()` para que una llamada
rechazada no cueste ni coerción ni `to_thread`.

Tres decisiones que no son obvias:

- **La llamada rechazada no incrementa `entry.calls`.** No llegó a la herramienta;
  cobrarla dejaría al bucle con la herramienta ocupada igual.
- **El límite es por herramienta, no global.** Si no, agotar una basta para
  bloquear todas.
- **El rechazo aparece en `audit()`.** Un límite que corta llamadas sin dejar
  rastro es indistinguible de uno que no existe, que es justo el fallo del que
  habla el Hueco 3.

Configurable con `AURA_TOOL_RATE_LIMIT` (llamadas, `120` por defecto, `<=0` lo
desactiva) y `AURA_TOOL_RATE_WINDOW` (segundos, `60`).

## 4. Hueco 3 — no hay dueño único del orquestador

`tama96` usa un lockfile (`~/.tama96/tama96.lock`) para que un solo proceso
posea la simulación. La TUI entra en "client mode" si la app de escritorio ya está
corriendo, en vez de duplicar el estado.

AURA tiene el problema exacto y peor: Electron (`v5/`), Tauri
(`aura-v5-tauri/`), la app de escritorio y el web pueden levantar el orquestador a
la vez. Duplicar una tarea no es un estado corrupto: es la misma acción ejecutada
dos veces.

Hay cobertura parcial: `aria_video_library/indexer.py` y
`ARIA_APP/backend/skills/registry.py` manejan locks. No hay un lock de ámbito
proceso para el orquestador.

### Punto de inserción

Un `SingleOwnerLock` se adquiere en el arranque del orquestador y se libera en el
shutdown. Dos casos adyacentes a decidir:

1. Si está tomado, el proceso nuevo **no** es dueño y degrada a cliente.
2. Si está tomado y el dueño no responde, hay que distinguir lock huérfano de
   lock vivo. `tama96` resuelve esto con un puerto local: el dueño escribe su
   puerto y el cliente se conecta. Es un patrón bueno y ya existe en el código de
   Tauri del proyecto, así que no es territorio nuevo.

## 5. Fase 3 — el gate que no confía en el exit code

De `strix/AGENTS.md`, la advertencia que más importa:

> A `0` only covers what was analyzed — check `run.json` (`status`,
> `llm_usage.cost` vs the budget) before calling a run clean.

Es decir: **código de salida 0 no significa "limpio", significa "terminó sin
fallar"**. El veredicto está en el artefacto.

También usan códigos explícitos: `0` limpio, `1` error fatal, `2` vulnerabilidades
encontradas, y `--max-budget` para cortar por coste.

### Qué se aplica a los gates de AURA

Los gates actuales (`tests/gates/`, `tests/test_*.py`) confían en que pytest salga
con 0. Eso no detecta un gate que se quedó en `skip`, un `xfail`, o un test que
dejó de ejecutar. El principio correcto es: **el gate tiene que producir un
artefacto y hay que leerlo.**

Implementado en `tests/gates/test_gate_integrity.py`: cuenta los tests collected
esperados, falla si la colección baja, y falla si hay `skip`/`xfail` sin una nota
explícita de por qué.

El mismo principio aplicado a las copias de `ai_providers.py`
(`tests/gates/test_ai_providers_sync.py`): la resolución de modelos vive en cuatro
archivos y la deriva entre ellos es silenciosa, porque cada copia es un archivo
válido por sí mismo. El gate compara el cuerpo de las cuatro, ignorando la
primera línea, que es el docstring de branding y difiere a propósito ("AURA" en la
raíz, "ARIA" en las copias). También falla si aparece una quinta copia sin
registrar: una copia sin vigilar es una copia que deriva.

### Salida SARIF

`strix` emite `findings.sarif` (SARIF 2.1.0). Para AURA tiene sentido el día que
los gates reporten a una herramienta externa de CI; hoy los `pytest` activos con
`-q` bastan. **No se implementa SARIF todavía**: sería formato sin consumidor.

---

## Decisión de orden

1. ~~**Hueco 2 (rate limit)**~~ — **hecho**. Era el más barato y el de mayor daño
   si falta: un bucle de agente que dispara herramientas sin parar.
2. **Hueco 1 (allow/deny)** — el que más superficie de seguridad abre, y el que
   más puede romper capacidades existentes. Necesita decidir la política por
   herramienta, no solo el mecanismo.
3. **Hueco 3 (lockfile)** — importante, pero depende de saber cuáles frontends
   deben poder correr a la vez.

Nada de esto toca el camino del chat, así que es independiente del cambio de
modelo de texto ya aplicado.
