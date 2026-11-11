# REPORTE PARA CLAUDE — Proceso de Razonamiento de ARIA con Matemáticas

**Fecha:** 2026-11-11  
**Autor:** Kilo  
**Repositorio:** AURA (rama `feat/aria-unified`)  
**Destino:** Revisión por Claude  

---

## 1. Qué se implementó

Se creó `ARIA_APP/backend/aria_brain/math_reasoning.py` — un adaptador que conecta el razonamiento de ARIA con la skill de matemáticas (`math.py`), para que cuando ARIA razone sobre una situación que contenga una operación numérica, use un resultado **verificable** en lugar de una suposición.

También se integró `MathReasoning` en `AriaBrain` (`ARIA_APP/backend/aria_brain/__init__.py`), de modo que `think_and_decide()` ahora incluye un campo `math` con el resultado del razonamiento matemático (si aplica).

---

## 2. Flujo de razonamiento

```
situacion (texto)
   |
   v
MathReasoning.detectar_operacion()  --> detecta patrones numéricos (suma, resta, *, /, !, raiz, primo, fibonacci, mcd, mcm, goldbach)
   |
   +-- None (no hay matemáticas) --> tiene_matematicas: false
   |
   +-- operación detectada
         |
         v
MathReasoning._run_math("math", params)  --> invoca la skill math (stdlib)
         |
         +-- status != ok  --> verificado: false, honesto: error
         |
         +-- resultado es None con error  --> verificado: false, honesto: mensaje
         |
         +-- resultado válido  --> verificado: true, honesto: confirmación
```

El resultado se devuelve como:
```json
{
  "tiene_matematicas": true,
  "operacion": "suma",
  "resultado": {"status": "ok", "skill": "math", "operacion": "suma", "a": 23.0, "b": 47.0, "resultado": 70.0, "nivel": "simple"},
  "verificado": true,
  "honesto": "Resultado verificado por la skill de matemáticas (stdlib)."
}
```

---

## 3. Detección de operaciones (patrones regex)

La función `detectar_operacion()` reconoce estos patrones en texto natural:

| Patrón ejemplo | Operación |
|----------------|-----------|
| `23 + 47` | suma |
| `100 / 4` | división |
| `es primo 97` | es_primo |
| `fibonacci de 10` | fibonacci |
| `mcd de 48 y 18` | mcd |
| `mcm de 12 y 18` | mcm |
| `raiz de 25` | raiz |
| `5 !` | factorial |
| `goldbach de 28` | verificar_goldbach |

Si no hay coincidencia, devuelve `None` y ARIA no intenta forzar una respuesta matemática.

---

## 4. Honestidad contractual (regla de ARIA)

- **Nunca inventar:** si la skill devuelve error o `resultado: None`, `verificado` es `false` y `honesto` explica por qué.
- **No adivinar números:** `detectar_operacion` solo extrae números que están explícitamente en el texto.
- **Problemas abiertos:** si se detecta `goldbach` para un par, se verifica ese par concreto (no se afirma la conjetura general).
- **División entre cero, raíz de negativo, factorial de negativo:** se manejan como errores honestos, no como fallos silenciosos.

---

## 5. Integración en AriaBrain

`AriaBrain.__init__` ahora tiene `self.math = MathReasoning()`.

`think_and_decide(situation)` ahora:
1. Llama a `self.reasoning.reason_about(situation)` (razonamiento simbólico existente)
2. Llama a `self.math.razonar_con_matematicas(situation)` (razonamiento numérico verificable)
3. Incluye el resultado en el dict de retorno bajo la clave `"math"`

---

## 6. Archivos modificados/creados

- `ARIA_APP/backend/aria_brain/math_reasoning.py` — nuevo (151 líneas)
- `ARIA_APP/backend/aria_brain/__init__.py` — modificado (import + campo math en retorno)
- `ARIA_APP/backend/skills/system/math.py` — creado previamente (skill matemática)
- `ARIA_APP/backend/skills/registry.py` — modificado (registro de skill math)

---

## 7. Diferencias Kilo vs Claude (recordatorio)

| Dimensión | Claude | Kilo |
|-----------|--------|------|
| Servidores/localhost | Prohibido en ARIA | Prohibido en ARIA (regla v2) |
| Dependencias nuevas | Prohibido (reportar como DEPENDENCIA PROPUESTA) | Prohibido (solo stdlib) |
| Matar procesos del usuario | Prohibido | Prohibido (regla inviolable) |
| Salida a internet desde skills | Permitido (urllib, PermissionEngine, logueado) | Permitido (mismo) |
| LLM local | Prohibido (nada localhost:11434) | Prohibido (mismo) |

---

## 8. Tareas pendientes para Claude

1. **Revisar** que `math_reasoning.py` no rompa el flujo existente de `AriaBrain`.
2. **Añadir más patrones de detección** si se necesitan (ej. potencias, logaritmos, trigonometría básica).
3. **Añadir tests** para `math_reasoning` y para la integración en `AriaBrain`.
4. **Conectar** el campo `math` del retorno de `think_and_decide` con la generación de explicación (`explanation_generator`) para que el usuario vea el resultado matemático verificado.
5. **Verificar** que no haya import circular entre `math_reasoning` y `skills.registry` (el import es diferido para evitarlo).

---

**Fin del reporte.**
