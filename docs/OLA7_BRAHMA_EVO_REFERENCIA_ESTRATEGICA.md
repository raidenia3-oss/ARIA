# Brahma Evo como referencia estrategica — ARIA v6

Comparativa escrita tras Ola 7. Distingue **verificado leyendo el repo** de
**afirmacion del brief original que resulto falsa**. Nada de esta tabla es
suposicion: cada fila indica como se comprobo.

## Estado de Ola 7 (P0 `/api/chat`)

Ejecutada y verificada. Changes staged, sin commit.

| Verificacion | Antes | Ahora |
|---|---|---|
| `tests/test_mobile_endpoints.py::TestChatEndpoint::test_chat_returns_200_without_name_error` | FAILED (AttributeError) | **1 passed** |
| Collection | 2472 | **2477**, 0 errores |
| Contratos + mobile | 68 + 1 fallo | **87 passed** |

Causa raiz: `backend/automation/__init__.py` reexportaba el singleton de
`engine.py` como `automation_engine`, pero existia un segundo modulo con el
mismo leaf-name, `automation_engine.py`. Importar un submodulo **rebinda el
atributo del paquete** y lo pisa. `main.py:99` importa `aura_daemon` (que
importaba ese submodulo) antes del singleton en `main.py:130`, asi que
`check_and_execute` no existia: `/api/chat` devolvia 500 siempre.

Fix: `automation_engine.py` -> `workflow_engine.py`, clase `AutomationEngine` ->
`WorkflowEngine`. Los dos motores **no eran duplicados**: sus APIs son disjuntas
(12 metodos rules vs 4 metodos workflows) y ambos tenian consumidores.

## Inventario verificado

| Afirmacion del brief | Realidad | Como se comprobo |
|---|---|---|
| "`computer.rs` tiene screenshot pero mentia" | Falso. Devuelve 501 via `control::not_implemented` desde Ola 3 | `v6/axum-poc/src/computer.rs:49,53,62,69` |
| "`v5/web.rs` existe pero es mentira" | Falso. El fichero no existe | `Test-Path v5\web.rs` -> False |
| "`/api/skills/*` (backend)" | No existe en el backend activo. Skills viven en `ARIA_APP/backend/skills` y routers swarm (`/skills`, no `/api/skills`) | grep `/api/skills` -> 0 en `backend/main.py` |
| "State: `cerebro.db`" | Solo existe en el subproyecto `ARIA_v4/AURA_APP/data/`, no en el backend v6 | glob `cerebro*.db` |
| "ARIA v6 es Axum (async Rust)" | El backend servido es FastAPI/Python. Axum es POC en 8002 | `backend/main.py` vs `v6/axum-poc` |
| "4 routers IA duplicados" | 3 routers (`backend/ai_router.py`, `integrations/plugins/ai_router.py`, mas `AIProviderManager` en `ai_providers.py` y `ARIA_APP/ai_providers.py`) + `aura_app.py`, que es una app GUI, no un router | grep de clases |
| "Jan + Ollama + Mistral + OpenRouter" | Declarados: `ollama` (dolphin-2_6-phi-2), `openrouter`, `local_openai`, `gemini`, `groq`, `huggingface`. **No hay Jan ni Mistral** | `ai_providers.py:27-33` |
| "Ollama local primero" | Cierto y medido: `_detect_providers` sondea `_check_endpoint` antes de marcar disponible | `ai_providers.py:49-64` |

Un matiz: `LOCAL_LFM_BASE_URL` marcada marca Ollama disponible sin sondear
(`ai_providers.py:51`). Con la variable puesta y el endpoint caido, declararia
disponibilidad sin medir. No es una fabricacion activa, pero es una excepcion
al patron.

## Lo que ARIA ya tiene (verificado)

- **Local-first real**: disponibilidad por sondeo, no declarada.
- **Contratos honestos**: 501 para accion no implementada, `data_source:
  "unavailable"` para telemetria no medida, `None` en vez de ceros.
- **Multi-provider con cadena de fallback** declarada y ordenada
  (`ai_providers.py:45`).
- **Auth fail-closed** en rutas de admin (`require_admin_token`).
- **Skills**: registro y dispatch en swarm y agent harness, **sin generador**.

## Lo que NO tiene (no es "parcial", es ausente)

- Generador de skills (self-modifying). El registry existe; la generacion no.
- Loop vision+accion coordinado. `/api/computer/*` es 501 en Axum; no hay
  endpoint de descripcion de pantalla conectado a un ejecutor de accion.
- Maquina de estados de browser multi-paso. Sin fichero que la contenga.

## Patron a adoptar (skill lifecycle)

El unico patron de Brahma que aporta algo que ARIA no tiene es el ciclo
get-or-generate. Traduccion honesta para ARIA, sin inventar funcionalidad:

1. Buscar skill en el registry.
2. Si falta: generar, **registrar**, y marcar la fuente como generada (no como
   nativa) para que la UI distinga.
3. Ejecutar.
4. Cachear resultado con la skill.

Falta decidir quien genera: si es un LLM, su output es codigo ejecutado. Eso
exige sandboxing antes de Phase D, no despues.

## Roadmap corregido

| Phase | Blocker real | Status |
|---|---|---|
| Ola 7 commit | staging listo, sin commit | pendiente de tu commit |
| v6.0-backend | gates Python/Rust/TS verdes | **listo** |
| v6.0-dart | `pc_state.dart` fabrica puerto/version/estado; sin Flutter SDK | **bloqueado** |
| Phase C | unificar routers; `backend/llm/` sin trackear | semana 1 |
| Phase D | loop vision+accion, browser state machine, skill generator | 2-3 sprints |
| Phase E | IoT/Zigbee | opcional |

## Decisiones abiertas que el brief daba por hechas

1. **`backend/llm/` como fuente de verdad**: sigue sin decidir. No es solo
   "trackearlo"; hay que elegir entre `engine.py`-style y el patron de adapters.
2. **Dart en el release**: Opcion A (Flutter, ~30-50 min, verificado) o C
   (Dart fuera del release, etiquetado honestamente). Opcion B descartada.
3. **`/api/orchestrator`**: dos handlers, ambos con auth, sin bypass. Ganador sin
   decidir; el perdedor es codigo muerto.