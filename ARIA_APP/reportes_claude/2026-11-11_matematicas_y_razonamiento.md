# REPORTE PARA CLAUDE — ARIA Matemáticas y Razonamiento

**Fecha:** 2026-11-11  
**Autor:** Kilo  
**Repositorio:** AURA (rama `feat/aria-unified`)  
**Destino:** Revisión por Claude  

---

## 1. Resumen ejecutivo

Se creó una skill de matemáticas para ARIA (`ARIA_APP/backend/skills/system/math.py`) y se registró en el `SkillRegistry`. Se investigaron problemas matemáticos apropiados para ARIA considerando sus restricciones (solo stdlib, sin servidores, honestidad contractual, desktop standalone). Se documentan también las diferencias de capacidades entre Kilo y Claude para que Claude sepa qué puede esperar de este reporte.

---

## 2. Problemas matemáticos apropiados para ARIA

### Criterios de selección

ARIA es una app de escritorio PyQt5 en un solo proceso, sin servidores, sin dependencias nuevas (solo stdlib), y con una regla de honestidad estricta: **nunca inventar datos, decir lo que no se sabe**. Por tanto, los problemas matemáticos apropiados son:

| Criterio | Justificación para ARIA |
|----------|------------------------|
| Computable con stdlib | `math`, `fractions`, `decimal` están disponibles sin `pip install` |
| Verificable localmente | No requiere internet ni APIs externas |
| Resultado exacto o acotado | `Fraction` da exactitud racional; `Decimal` controla precisión |
| Honestidad sobre lo abierto | Problemas no resueltos se marcan como `sabido: false`, sin solución inventada |
| Relevante para su contexto | Enlace ASAGI, memoria, razonamiento, verificación de claims |

### Niveles implementados (en `math.py`)

**Simple:** suma, resta, multiplicación, división, potencia, raíz, factorial  
**Intermedio:** MCD, MCM, es_primo, descomposición prima, siguiente primo, Fibonacci  
**Avanzado:** verificar Goldbach (par concreto), serie armónica parcial, constante e, pi por Leibniz  
**Abierto / no resuelto:** conjetura de Goldbach, primos gemelos, hipótesis de Riemann, P vs NP, Collatz, Erdős-Straus

### Problemas abiertos documentados (sin solución inventada)

Cada uno tiene `sabido: false`, `resultado: None`, enunciado, estado real, y una nota de honestidad. ARIA nunca afirma haber resuelto ninguno.

---

## 3. Proceso de razonamiento de ARIA (estado actual)

Existe `ARIA_APP/backend/aria_brain/reasoning_engine.py` con un `ReasoningEngine` que implementa:
- Razonamiento lógico, abductivo, analógico, causal, contrafactual
- Síntesis de conclusiones
- Razonamiento multi-paso con scoring de confianza

**Limitación observada:** El motor no integra matemáticas verificables como parte de su cadena de razonamiento. Las reglas son cadenas de texto sin comprobación numérica.

**Propuesta (pendiente de implementar):** Extender `ReasoningEngine` para que, cuando detecte una cuestión numérica en el problema, invoque la skill `math` y use el resultado como hecho verificable en lugar de una suposición.

---

## 4. Diferencias de capacidades: Kilo vs Claude

Esta sección es importante porque Claude tiene limitaciones impuestas que Kilo no tiene, y viceversa. Claude debe leer esto antes de actuar sobre este reporte.

| Dimensión | Claude (limitaciones impuestas) | Kilo (sin esas limitaciones) |
|-----------|--------------------------------|------------------------------|
| Servidores / localhost | **Prohibido:** no puede abrir puertos, no `bind/listen`, no `127.0.0.1`, no Ollama local, no FastAPI/uvicorn servidor | **Misma restricción:** ARIA también es regla v2 (sin servidores, sin localhost) |
| Dependencias nuevas | **Prohibido:** no instalar paquetes por cuenta propia; reportar como "DEPENDENCIA PROPUESTA" | **Misma restricción:** solo stdlib para skills de ARIA |
| Internet para arrancar | **Prohibido:** ARIA debe arrancar sin red | **Misma restricción** |
| Interfaz en navegador | **Prohibido:** no HTML servido | **Misma restricción** |
| Salida a internet desde skills | **Permitido:** urllib.request/http.client/ssl, pasando por PermissionEngine, logueado, fail-closed | **Misma restricción** |
| LLM local | **Prohibido:** nada de localhost:11434 (Ollama, etc.) | **Misma restricción** |
| Matar procesos del usuario | **Prohibido:** nunca `taskkill /IM`, `pkill`, cerrar navegadores del usuario | **Misma restricción** (regla inviolable del 2026-10-19) |
| Acceso a archivos locales | Permitido (SQLite, archivos, data/) | Permitido |
| Subprocesos del sistema | Permitido con permiso (nmap, whois, tor, tcpdump) | Permitido con permiso |
| Commit / push | Puede comitear y pushear en ramas específicas | Puede comitear y pushear en ramas específicas |
| Contexto de memoria | Tiene acceso a kilo-memory (project.md, corrections.md, session digests) | Tiene acceso a kilo-memory |
| Crear habilidades nuevas | Puede, pero solo stdlib, sin servidores | Puede, solo stdlib, sin servidores |

### Qué implica esto para Claude

1. **No proponga servidores locales ni Ollama** para nada relacionado con ARIA. Todo razonamiento y matemáticas debe ser in-process, stdlib.
2. **No instale paquetes** (`pip install`) para extensiones de ARIA. Si necesita algo fuera de stdlib, debe reportarlo como "DEPENDENCIA PROPUESTA".
3. **No abra puertos** ni use `127.0.0.1` para pruebas.
4. **No mate procesos del usuario** bajo ninguna circunstancia.
5. **La honestidad matemática es contractual:** si Claude extiende la skill `math`, debe mantener `sabido: false` para problemas abiertos y nunca inventar soluciones.

---

## 5. Tareas pendientes para Claude (si decide continuar)

1. **Integrar `math` en `ReasoningEngine`:** cuando `reason_about` detecte entidades numéricas, invocar la skill `math` y tratar el resultado como hecho verificable.
2. **Añadir más operaciones matemáticas** si es necesario (ej. ecuaciones de segundo grado, logaritmos, trigonometría básica con `math`).
3. **Añadir tests** para la skill `math` en `tests/` siguiendo el patrón existente.
4. **Documentar** la skill `math` en la ayuda de ARIA (comandos disponibles).
5. **Revisar** que ningún problema abierto en `ABIERTOS` afirme tener solución.

---

## 6. Archivos creados/modificados

- `ARIA_APP/backend/skills/system/math.py` — nueva skill de matemáticas (stdlib, honesta)
- `ARIA_APP/backend/skills/registry.py` — registro de la skill `math`
- `ARIA_APP/reportes_claude/` — carpeta de reportes (este archivo)

Commit: `2a127d7` en `feat/aria-unified` (pushado a `origin/feat/aria-unified`)

---

**Fin del reporte.** Claude: si revisa esto, confirme recepción y indique qué tareas acepta.
