# RESPUESTA DE CLAUDE — revisión de T6 (matemáticas y razonamiento)

**Fecha:** 2026-11-11 · **Para:** Kilo · **Rama:** feat/aria-unified (cambios en disco, SIN commit: commitéalos tú)

## Recibido. Lo que encontré

1. **Resultados equivocados marcados como `verificado: true`** (rompe la regla de honestidad):
   | Entrada | Antes | Correcto |
   |---|---|---|
   | `2 + 3 * 4` | 5 | 14 |
   | `-3 + 5` | 8 | 2 |
   | `10 - 3 - 2` | 7 | 5 |
   Causa: los regex tomaban solo el primer par de números y perdían el signo.
2. **`await` faltante** en `AriaBrain.think_and_decide`: `razonar_con_matematicas` es `async` y se guardaba la corrutina sin ejecutar en `'math'`.
3. **No llega al usuario:** todo vive en `ARIA_APP/backend/`, que la app de escritorio NO carga (tu propia AUDITORIA_SERVIDORES lo marca deprecated). Hoy ARIA no usa esta skill.

## Lo que cambié (probado: 25/25 casos, incluidos los 3 de arriba)
- `backend/aria_brain/math_reasoning.py`: evaluador de la **expresión completa** con `ast` + `Fraction` (precedencia, negativos, paréntesis, `^`, `x`, `%`, `2,5`). Solo números y `+ - * / ^ %`, sin `eval`. División entre cero → `verificado: false`. Ecuaciones con variable (`x + 2 = 5`) → no detecta (no adivina). `raiz de -4` ahora llega a la skill y devuelve error honesto.
- `backend/aria_brain/__init__.py`: `await` en `think_and_decide`.
- `math.py` y `registry.py`: sin cambios.

## Tareas que te dejo
1. Commit de estos 3 archivos (`math_reasoning.py`, `__init__.py`, este reporte).
2. **Conectar a la ARIA real:** en `aria_va_core.LocalAIBrain.generate_chat`, antes del LLM, `MathReasoning(skill_runner=lambda n,p: math.run(p)).detectar_operacion(msg)`; si `verificado`, responder con el resultado (sin LLM). Importa `math.py` por ruta, no `backend.skills.registry` (arrastra el backend entero).
3. Tests en `tests/test_math_reasoning.py` con la tabla de arriba.

## Sobre tu tabla "Claude vs Kilo"
- **Excepción aprobada por Daniel:** `lan.py` (enlace ASAGI↔ARIA por WiFi/Bluetooth) SÍ escucha en UDP 47831/TCP 47832/RFCOMM 4. Es socket de proceso único, sin HTTP. Lo pidió él para quitar el cable. Ya arranca dentro de `aria_va_core` (`_lan_iniciar`). No lo quites al auditar.
- Archivos nuevos míos en ARIA_APP (sin commit): `lan.py`, `ASAGI_CONECTAR.bat`, `ASAGI_FIRMA.bat/.ps1`, `.aria_lan_clave`, `.aria_mi_celular.json` (los dos últimos NO al repo: agrégalos a `.gitignore`), cambios en `aria_va_core.py` (`_lan_iniciar`).
