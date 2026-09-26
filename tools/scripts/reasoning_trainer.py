#!/usr/bin/env python3
"""
AURA Reasoning Trainer — Área de razonamiento avanzado para el espacio de entrenamiento.

Genera problemas de:
  - Razonamiento lógico formal y silogismos
  - Matemáticas con solución paso a paso (Chain-of-Thought)
  - Programación: debugging, implementación, optimización
  - Planificación y secuenciación de tareas
  - Causalidad y contrafactuales

Uso:
  python scripts/reasoning_trainer.py --count 100 --domains logic,math,code
  python scripts/reasoning_trainer.py --output training-data-reasoning.jsonl --difficulty hard
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ReasoningTrainer")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-reasoning.jsonl"

REASONING_TEMPLATES: Dict[str, List[Dict]] = {
    "logic": [
        {
            "template": (
                "Todos los {A} son {B}. Algunos {B} son {C}. "
                "Por lo tanto, algunos {A} son {C}. "
                "¿Es esta conclusión válida? Explica paso a paso."
            ),
            "variables": {
                "A": ["gatos", "perros", "pájaros", "peces", "robots", "programadores", "científicos", "ingenieros"],
                "B": ["mamíferos", "animales", "seres vivos", "sistemas", "agentes", "entidades", "procesos", "dispositivos"],
                "C": ["domésticos", "salvajes", "inteligentes", "rápidos", "complejos", "autónomos", "conectados", "eficientes"],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Formalizar premisas.\n"
                "P1: ∀x (A(x) → B(x))\n"
                "P2: ∃x (B(x) ∧ C(x))\n"
                "Conclusión: ∃x (A(x) ∧ C(x))\n\n"
                "Paso 2: Evaluar validez. De P1 y P2 no se sigue necesariamente la conclusión. "
                "Contraejemplo: Algunos {B} son {C}, pero no todos los {A} son {B} en la intersección necesaria.\n\n"
                "Respuesta: Inválida. Se requiere información adicional para garantizar la conclusión."
            ),
        },
        {
            "template": (
                "Si {A}, entonces {B}. Si {B}, entonces {C}. {A} es verdadero. "
                "¿Qué puedes concluir sobre {C}? Justifica formalmente."
            ),
            "variables": {
                "A": ["llueve", "el sistema está activo", "el usuario está autenticado", "el servidor responde", "el contrato se despliega"],
                "B": ["el suelo está mojado", "se ejecuta el script", "se concede acceso", "se envía la respuesta", "se activa el monitoreo"],
                "C": ["necesitamos paraguas", "se completa la tarea", "el usuario ve el dashboard", "el cliente recibe el dato", "se registra el evento"],
            },
            "difficulty": "easy",
            "answer": (
                "Paso 1: Formalizar.\n"
                "P1: A → B\n"
                "P2: B → C\n"
                "P3: A (verdadero)\n\n"
                "Paso 2: Aplicar Modus Ponens.\n"
                "De P1 y P3: {B}.\n"
                "De P2 y B: {C}.\n\n"
                "Conclusión: {C} es verdadero por silogismo hipotético."
            ),
        },
        {
            "template": (
                "Un sistema tiene {n} componentes. Cada componente falla independientemente "
                "con probabilidad {p}. ¿Cuál es la probabilidad de que el sistema falle "
                "si funciona mientras al menos un componente funcione?"
            ),
            "variables": {
                "n": [3, 5, 10, 20],
                "p": [0.01, 0.05, 0.1, 0.2],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Probabilidad de que un componente NO falle: q = 1 - p.\n"
                "Paso 2: Probabilidad de que TODOS funcionen: q^n.\n"
                "Paso 3: Probabilidad de fallo del sistema = 1 - q^n.\n"
                "Interpretación: Con {n} componentes y tasa de fallo individual {p}, "
                "el sistema tiene una fiabilidad muy alta para {n} pequeño."
            ),
        },
        {
            "template": (
                "Tres interruptores controlan una lámpara en otra habitación. Solo puedes entrar una vez. "
                "¿Cómo determinar cuál interruptor enciende la lámpara? Explica la estrategia."
            ),
            "variables": {},
            "difficulty": "medium",
            "answer": (
                "Estrategia óptima:\n"
                "1. Encender el interruptor 1 y dejarlo encendido durante 5-10 minutos.\n"
                "2. Apagar el interruptor 1 y encender el interruptor 2.\n"
                "3. Entrar a la habitación.\n"
                "   - Si la lámpara está encendida → Interruptor 2.\n"
                "   - Si está apagada pero caliente → Interruptor 1.\n"
                "   - Si está apagada y fría → Interruptor 3.\n\n"
                "Razonamiento: Usamos el estado térmico como tercera variable de discriminación."
            ),
        },
        {
            "template": (
                "En una carrera, adelantas al segundo. ¿En qué posición terminas? "
                "Explica por qué mucha gente responde mal."
            ),
            "variables": {},
            "difficulty": "easy",
            "answer": (
                "Respuesta: Quedas en segundo lugar.\n\n"
                "Razonamiento:\n"
                "- Si adelantas al segundo, ocupas su lugar.\n"
                "- Por tanto, pasas de tercera a segunda posición.\n\n"
                "Por qué mucha gente falla:\n"
                "Sesgo de respuesta rápida: asumen que 'adelantar al segundo' implica automáticamente "
                "ser primero, ignorando que el primero sigue adelante."
            ),
        },
        {
            "template": (
                "Un granjero tiene {n} animales entre {A} y {B}. Cuenta {legs} patas y {heads} cabezas. "
                "¿Cuántos {A} y cuántos {B} hay? Resuelve el sistema de ecuaciones."
            ),
            "variables": {
                "n": [100, 200, 50],
                "A": ["gallinas", "conejos", "patos", "palomas"],
                "B": ["cerdos", "liebres", "gansos", "pollos"],
                "legs": [220, 560, 140],
                "heads": [100, 200, 50],
            },
            "difficulty": "easy",
            "answer": (
                "Sistema:\n"
                "x + y = {heads}\n"
                "{legs_A}x + {legs_B}y = {legs}\n\n"
                "Resolución:\n"
                "Despejar y = {heads} - x\n"
                "Sustituir: {legs_A}x + {legs_B}({heads} - x) = {legs}\n"
                "Resolver para x e y.\n\n"
                "Interpretación: Se valida que x + y = {heads}."
            ),
        },
    ],
    "math": [
        {
            "template": (
                "Calcula el límite de {expr} cuando {var} tiende a {val}. "
                "Muestra el desarrollo paso a paso."
            ),
            "variables": {
                "expr": ["(x^2 - 1)/(x - 1)", "sin(x)/x", "(1 - cos(x))/x^2", "(e^x - 1)/x", "ln(1 + x)/x"],
                "var": ["x", "x", "x", "x", "x"],
                "val": ["1", "0", "0", "0", "0"],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Sustituir directamente y verificar forma indeterminada.\n"
                "Paso 2: Aplicar regla de L'Hôpital o factorización algebraica.\n"
                "Paso 3: Recalcular el límite tras la transformación.\n"
                "Paso 4: Verificar resultado analítica y gráficamente."
            ),
        },
        {
            "template": (
                "Deriva {expr} respecto a {var}. Simplifica el resultado."
            ),
            "variables": {
                "expr": ["x^3 * e^x", "ln(x^2 + 1)", "sin(x) * cos(x)", "x/(x^2 + 1)", "(1 + x^2)^(1/2)"],
                "var": ["x", "x", "x", "x", "x"],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Identificar regla de derivación (producto, cadena, cociente).\n"
                "Paso 2: Aplicar regla paso a paso.\n"
                "Paso 3: Simplificar expresión algebraica.\n"
                "Paso 4: Verificar derivando el resultado (si es posible)."
            ),
        },
        {
            "template": (
                "Un proyecto cuesta ${n} y se deprecia un {p}% anual. "
                "¿Cuánto valdrá después de {t} años con depreciación compuesta?"
            ),
            "variables": {
                "n": [10000, 50000, 25000],
                "p": [10, 15, 20],
                "t": [3, 5, 10],
            },
            "difficulty": "easy",
            "answer": (
                "Fórmula: V = P * (1 - r)^t\n"
                "Paso 1: Convertir porcentaje a decimal: r = {p}/100.\n"
                "Paso 2: Aplicar fórmula de depreciación compuesta.\n"
                "Paso 3: Calcular resultado final.\n"
                "Paso 4: Interpretar en contexto económico."
            ),
        },
        {
            "template": (
                "Calcula la probabilidad de obtener al menos un {A} en {n} lanzamientos "
                "de un dado justo de {s} caras."
            ),
            "variables": {
                "A": ["6", "número par", "número primo", "1 o 2"],
                "n": [3, 5, 10],
                "s": [6, 8, 12],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Calcular probabilidad de NO obtener {A} en un lanzamiento.\n"
                "Paso 2: Elevar a la potencia n para n lanzamientos independientes.\n"
                "Paso 3: Complemento: P(al menos uno) = 1 - P(ninguno).\n"
                "Paso 4: Aproximar o calcular exactamente según valores."
            ),
        },
        {
            "template": (
                "Dada la función f(x) = {expr}, encuentra el valor de x que maximiza f(x) "
                "en el intervalo [{a}, {b}]. Verifica que es un máximo."
            ),
            "variables": {
                "expr": ["-x^2 + 4x + 5", "x * e^{-x}", "ln(x) - x", "-2x^3 + 3x^2 + 12x"],
                "a": [0, 0, 1, -2],
                "b": [5, 5, 10, 3],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Calcular derivada f'(x).\n"
                "Paso 2: Encontrar puntos críticos f'(x) = 0.\n"
                "Paso 3: Evaluar f(x) en puntos críticos y extremos del intervalo.\n"
                "Paso 4: Aplicar test de segunda derivada para confirmar máximo.\n"
                "Paso 5: Verificar condiciones de frontera."
            ),
        },
    ],
    "code": [
        {
            "template": (
                "Escribe una función en Python que {A}. "
                "Luego, optimízala para reducir su complejidad temporal. "
                "Explica los cambios."
            ),
            "variables": {
                "A": [
                    "encuentre el par de números más cercano en una lista",
                    "genere todas las permutaciones de una lista sin repetir",
                    "verifique si un string es un palíndromo ignorando espacios",
                    "implemente el algoritmo de Euclides para el máximo común divisor",
                    "dado un array, encuentre el subarray con suma máxima",
                ],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Implementación inicial O(n^2) o fuerza bruta.\n"
                "Paso 2: Identificar cuello de botella (comparaciones anidadas, búsqueda lineal).\n"
                "Paso 3: Aplicar estructura de datos optimizada (hash map, two pointers, DP).\n"
                "Paso 4: Presentar versión optimizada O(n log n) o O(n).\n"
                "Paso 5: Incluir tests unitarios y análisis de complejidad."
            ),
        },
        {
            "template": "Debuggea el siguiente código Python. Explica cada error y proporciona la versión corregida:\n\n{codigo}",
            "variables": {
                "codigo": [
                    "def add(a, b):\n    return a + b\n\nresult = add(1, '2')",
                    "def factorial(n):\n    return n * factorial(n)\n\nprint(factorial(5))",
                    "lst = [1, 2, 3]\nfor i in range(len(lst)):\n    print(lst[i+1])",
                    "x = input('num')\nif x > 10:\n    print('big')",
                    "def calcular_promedio(numeros):\n    total = 0\n    for n in numeros:\n        total += n\n    return total / len(numeros)\n\nprint(calcular_promedio([]))",
                ]
            },
            "difficulty": "easy",
            "answer": (
                "Error 1: [Tipo]. add() recibe int + str → TypeError en runtime.\n"
                "Corrección: Convertir a int o validar tipos antes de operar.\n\n"
                "Error 2: [Recursión infinita]. factorial(n) se llama a sí misma sin caso base.\n"
                "Corrección: Agregar if n <= 1: return 1.\n\n"
                "Error 3: [Índice fuera de rango]. lst[i+1] falla en la última iteración.\n"
                "Corrección: range(len(lst) - 1) o enumerate().\n\n"
                "Error 4: [Tipo]. input() devuelve str; comparación con int falla.\n"
                "Corrección: int(input('num')).\n\n"
                "Error 5: [División por cero]. len([]) = 0 → ZeroDivisionError.\n"
                "Corrección: Validar lista vacía antes de dividir."
            ),
        },
        {
            "template": (
                "Implementa un {A} en Python con las siguientes especificaciones: {B}. "
                "Incluye manejo de errores y tests unitarios básicos."
            ),
            "variables": {
                "A": ["cache LRU", "árbol binario de búsqueda", "stack con operación min() O(1)", "sistema de colas con prioridad", "parser de JSON simple"],
                "B": [
                    "capacidad {n}, operaciones get/put en O(1)",
                    "insercción, búsqueda y eliminación en O(log n)",
                    "push, pop y obtener mínimo en tiempo constante",
                    "encolar con prioridad, desencolar el de mayor prioridad",
                    "parsear strings JSON a objetos Python nativos",
                ],
                "n": [100, 1000, 50],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Definir interfaz pública y casos de uso.\n"
                "Paso 2: Seleccionar estructuras de datos subyacentes (OrderedDict, heapq, etc.).\n"
                "Paso 3: Implementar con type hints y docstrings.\n"
                "Paso 4: Agregar manejo de excepciones personalizadas.\n"
                "Paso 5: Escribir tests unitarios con pytest (casos normales, edge cases, errores)."
            ),
        },
        {
            "template": "Refactoriza el siguiente código para mejorar su legibilidad y mantenibilidad:\n\n{codigo}",
            "variables": {
                "codigo": [
                    "def f(d):\n    r={}\n    for k in d:\n        if d[k]>0:r[k]=d[k]\n    return r",
                    "data=[{'a':1},{'a':2},{'b':3}]\nresult=[]\nfor i in range(len(data)):\n    if data[i]['a'] not in [x['a'] for x in result]:\n        result.append(data[i])",
                    "def calc(a,b,c):\n    if a>b:\n        if b>c:\n            return a*b/c\n        else:\n            return a/b*c\n    else:\n        return b*c/a",
                ]
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Extraer nombres descriptivos (f → filter_positive, d → data_dict).\n"
                "Paso 2: Usar comprehensions o built-ins cuando corresponda.\n"
                "Paso 3: Eliminar código muerto y duplicación.\n"
                "Paso 4: Separar lógica en funciones pequeñas y testeables.\n"
                "Paso 5: Agregar type hints y docstrings."
            ),
        },
    ],
    "planning": [
        {
            "template": (
                "Planifica la implementación de {A} para un equipo de {n} desarrolladores "
                "con un plazo de {t} semanas. Considera riesgos, dependencias y entregables."
            ),
            "variables": {
                "A": ["una API REST de e-commerce", "un pipeline de CI/CD", "un sistema de recomendación", "una app móvil de delivery", "un dashboard de analíticas en tiempo real"],
                "n": [3, 5, 8, 12],
                "t": [2, 4, 8, 12],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Definir hitos (análisis, diseño, desarrollo, testing, deploy).\n"
                "Paso 2: Estimar esfuerzo por tarea y asignar recursos humanos.\n"
                "Paso 3: Identificar dependencias críticas (BD, APIs externas, infraestructura).\n"
                "Paso 4: Definir métricas de progreso (velocity, burndown, test coverage).\n"
                "Paso 5: Plan de contingencia para riesgos principales (cambio de requisitos, rotación, deuda técnica)."
            ),
        },
        {
            "template": (
                "Tienes {n} tareas con las siguientes duraciones y dependencias: {details}. "
                "Determina el camino crítico y la duración mínima del proyecto."
            ),
            "variables": {
                "n": [5, 7, 10],
                "details": [
                    "A(3d)→C(2d)→E(4d); B(2d)→D(3d)→E; F(1d)→G(2d)→E",
                    "Análisis(5d)→Diseño(3d)→Implementación(8d)→Testing(3d)→Deploy(1d); Diseño(3d)→Revisión(2d)",
                    "Investigación(4d)→Prototipo(6d)→Desarrollo(10d)→QA(4d)→Release(2d); Investigación(4d)→Documentación(3d)",
                ],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Construir grafo de dependencias (nodos = tareas, aristas = dependencias).\n"
                "Paso 2: Calcular earliest start/finish para cada nodo (hacia adelante).\n"
                "Paso 3: Calcular latest start/finish (hacia atrás).\n"
                "Paso 4: Holgura = LS - ES; camino crítico = nodos con holgura 0.\n"
                "Paso 5: Duración mínima = suma de duraciones en el camino crítico."
            ),
        },
        {
            "template": (
                "Un servidor maneja {n} solicitudes por segundo con latencia media de {lat}ms. "
                "Si la carga aumenta un {p}%, ¿qué estrategias aplicarías para mantener el SLA de {sla}ms?"
            ),
            "variables": {
                "n": [1000, 5000, 10000],
                "lat": [50, 100, 200],
                "p": [50, 100, 200],
                "sla": [100, 150, 300],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Calcular nueva carga esperada: {n} * (1 + {p}/100) = {new_load} req/s.\n"
                "Paso 2: Identificar cuello de botella (CPU, I/O, red, lock contention).\n"
                "Paso 3: Estrategias:\n"
                "   - Escalado horizontal (más instancias behind load balancer).\n"
                "   - Caching agresivo (Redis, CDN) para reducir llamadas a BD.\n"
                "   - Async/queues para operaciones no bloqueantes.\n"
                "   - Connection pooling y keep-alive.\n"
                "Paso 4: Validar con load testing antes de producción."
            ),
        },
    ],
    "causal": [
        {
            "template": (
                "Si el servidor A cae, el servicio B se desconecta. "
                "El servicio B se desconectó. ¿El servidor A necesariamente cayó? "
                "Explica razonando sobre correlación vs causalidad."
            ),
            "variables": {},
            "difficulty": "medium",
            "answer": (
                "No necesariamente. Se analiza con razonamiento lógico:\n"
                "P1: A → B (si A cae, B se desconecta)\n"
                "P2: B cayó\n"
                "Conclusión: A pudo haber caído, pero también pudo haber otra causa para B.\n\n"
                "Falacia: Afirmación del consecuente (asumir que el antecedente es verdadero solo porque el consecuente lo es).\n\n"
                "Próximo paso: Investigar otras causas posibles (red, dependencia externa, configuración)."
            ),
        },
        {
            "template": (
                "Un modelo predice {A} con 95% de precisión. Sin embargo, en producción "
                "falla el 40% de las veces. ¿Qué explicaciones causales consideras?"
            ),
            "variables": {
                "A": ["fraude en transacciones", "enfermedades raras", "fallos de servidor", "spam en correos", "incidentes de seguridad"],
            },
            "difficulty": "hard",
            "answer": (
                "Posibles causas:\n"
                "1. Data drift: distribución en producción difiere de entrenamiento.\n"
                "2. Muestra no representativa: clase desbalanceada no manejada (SMOTE, class weights).\n"
                "3. Label leakage: información del futuro en entrenamiento.\n"
                "4. Feedback loop: predicciones que afectan el sistema y cambian el comportamiento.\n"
                "5. Threshold mal calibrado para el negocio (precision vs recall trade-off).\n"
                "6. Concept drift: el fenómeno {A} evolucionó desde que se entrenó el modelo."
            ),
        },
        {
            "template": (
                "Tras actualizar la versión de Python de 3.9 a 3.11, los tests de integración "
                "fallan solo en el entorno de staging, pero no en development. "
                "Propón un método sistemático para aislar la causa raíz."
            ),
            "variables": {},
            "difficulty": "hard",
            "answer": (
                "Método de aislamiento:\n"
                "1. Definir hipótesis: dependencias, configuración, datos, código.\n"
                "2. Usar diff de entornos: pip freeze, variables de entorno, archivos de config.\n"
                "3. Ejecutar mismo test suite en staging con verbose output.\n"
                "4. Aplicar método científico: cambiar UNA variable a la vez.\n"
                "5. Documentar hallazgo y remediación."
            ),
        },
    ],
    "math_word": [
        {
            "template": (
                "Un tanque se llena por dos tuberías. La primera lo llena en {t1} horas, "
                "la segunda en {t2} horas. Si ambas se abren simultáneamente, ¿en cuánto tiempo "
                "se llena el tanque? Resuelve algebraicamente."
            ),
            "variables": {
                "t1": [6, 8, 10],
                "t2": [4, 5, 12],
            },
            "difficulty": "easy",
            "answer": (
                "Paso 1: Tasas de trabajo.\n"
                "Tubería 1: 1/{t1} del tanque por hora.\n"
                "Tubería 2: 1/{t2} del tanque por hora.\n"
                "Paso 2: Suma de tasas: 1/{t1} + 1/{t2} = {sum}.\n"
                "Paso 3: Tiempo conjunto = 1 / {sum} = {ans} horas.\n"
                "Interpretación: Verificar que sea menor que {min(t1, t2)}."
            ),
        },
        {
            "template": (
                "Un tren sale de la ciudad A hacia B a {v1} km/h. Otro sale de B hacia A {delay} horas después a {v2} km/h. "
                "La distancia es {d} km. ¿A qué distancia de A se encuentran?"
            ),
            "variables": {
                "v1": [60, 80, 100],
                "v2": [40, 70, 90],
                "delay": [1, 2, 3],
                "d": [300, 500, 700],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Calcular distancia que recorre el primer tren en {delay} horas.\n"
                "Paso 2: Distancia restante cuando el segundo tren arranca.\n"
                "Paso 3: Velocidad relativa: {v1} + {v2} = {v_rel} km/h.\n"
                "Paso 4: Tiempo hasta encuentro = distancia_restante / {v_rel}.\n"
                "Paso 5: Distancia desde A = ({v1} * ({delay} + t_encuentro))."
            ),
        },
    ],
}


class ReasoningTrainer:
    """Genera problemas de razonamiento avanzado para entrenamiento."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()

    def _key(self, domain: str, idx: int, difficulty: str) -> str:
        return f"{domain}:{idx}:{difficulty}"

    def _fill_template(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list):
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        remaining = re.findall(r"\{([A-Z]+)\}", result)
        for var in remaining:
            result = result.replace("{" + var + "}", f"[{var}]")
        return result

    def generate(self, domain: str, difficulty: Optional[str] = None) -> Dict:
        templates = REASONING_TEMPLATES.get(domain, [])
        if not templates:
            raise ValueError(f"Unknown domain: {domain}")

        if difficulty is None:
            difficulty = random.choice(["easy", "medium", "hard", "expert"])

        eligible = [t for t in templates if t.get("difficulty", "medium") == difficulty]
        if not eligible:
            eligible = templates

        template = random.choice(eligible)
        idx = templates.index(template)
        key = self._key(domain, idx, difficulty)

        if key in self.generated_keys:
            return self.generate(domain, difficulty)
        self.generated_keys.add(key)

        question = self._fill_template(template["template"], template.get("variables", {}))
        raw_answer = template.get("answer", self._default_answer(domain, difficulty))
        answer = self._fill_template(raw_answer, template.get("variables", {}))

        return {
            "text": question,
            "output": answer,
            "metadata": {
                "source": "reasoning_trainer",
                "domain": domain,
                "difficulty": difficulty,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def _default_answer(self, domain: str, difficulty: str) -> str:
        return (
            f"Respuesta estructurada para dominio '{domain}' con dificultad '{difficulty}'.\n"
            "Se incluye razonamiento paso a paso, verificación y conclusión."
        )

    def generate_batch(
        self,
        count: int = 50,
        domains: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
    ) -> List[Dict]:
        if domains is None:
            domains = list(REASONING_TEMPLATES.keys())

        results = []
        per_domain = max(1, count // len(domains))
        for domain in domains:
            for _ in range(per_domain):
                try:
                    results.append(self.generate(domain, difficulty))
                except Exception as exc:
                    logger.debug(f"Skip reasoning {domain}: {exc}")
        return results[:count]

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} reasoning samples -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    trainer = ReasoningTrainer(seed=42)
    domains = args.domains.split(",") if args.domains else None
    items = trainer.generate_batch(
        count=args.count,
        domains=domains,
        difficulty=args.difficulty,
    )
    output = Path(args.output)
    trainer.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Reasoning Trainer")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--domains", type=str, default=None, help="Dominios separados por coma")
    p.add_argument("--difficulty", type=str, default=None, choices=["easy", "medium", "hard", "expert"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
