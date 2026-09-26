#!/usr/bin/env python3
"""
AURA Task Simulation Engine — Entorno de simulación de tareas avanzadas.

Genera problemas complejos de razonamiento, código, matemáticas, planificación
y búsqueda avanzada en formato JSONL para entrenamiento del modelo.

Categorías de tareas:
  - logic       : Razonamiento lógico formal, silogismos, deducción
  - math        : Álgebra, cálculo, estadística, probabilidad
  - code        : Debugging, implementación, optimización, refactor
  - planning    : Planificación de proyectos, secuenciación, gestión recursos
  - search      : Búsqueda avanzada, formulación de queries, filtrado
  - analysis    : Análisis de datos, patrones, tendencias
  - synthesis   : Composición, diseño, arquitectura, integración

Uso:
  python scripts/task_simulation_engine.py --count 100 --categories logic,math,code
  python scripts/task_simulation_engine.py --output training-data-tasks.jsonl --difficulty hard
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
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TaskSimEngine")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-tasks.jsonl"

DIFFICULTY_LEVELS = ["easy", "medium", "hard", "expert"]

TASK_TEMPLATES: Dict[str, List[Dict]] = {
    "logic": [
        {
            "template": "Todos los {A} son {B}. Algunos {B} son {C}. Por lo tanto, algunos {A} son {C}. ¿Es esta conclusión válida? Explica tu razonamiento paso a paso.",
            "variables": {
                "A": ["gatos", "perros", "pájaros", "peces", "insectos", "robots", "programadores", "científicos"],
                "B": ["mamíferos", "animales", "seres vivos", "sistemas", "procesos", "agentes", "entidades", "dispositivos"],
                "C": ["domésticos", "salvajes", "inteligentes", "rápidos", "grandes", "pequeños", "complejos", "conectados"],
            },
            "difficulty": "medium",
            "answer": (
                "Paso 1: Formalizar premisas.\n"
                "P1: ∀x (A(x) → B(x))\n"
                "P2: ∃x (B(x) ∧ C(x))\n"
                "Conclusión: ∃x (A(x) ∧ C(x))\n\n"
                "Paso 2: Evaluar validez. De P1 y P2 no se sigue necesariamente la conclusión. "
                "Se requiere información adicional sobre la intersección entre {A} y {C} dentro de {B}.\n\n"
                "Respuesta: Inválida sin información adicional."
            ),
        },
        {
            "template": "Si {A}, entonces {B}. Si {B}, entonces {C}. {A} es verdadero. ¿Qué puedes concluir sobre {C}? Justifica.",
            "variables": {
                "A": ["llueve", "el sistema está activo", "el usuario está autenticado", "la puerta está cerrada", "el servidor responde"],
                "B": ["el suelo está mojado", "se ejecuta el script", "se concede acceso", "no hay corriente de aire", "se envía la respuesta"],
                "C": ["necesitamos un paraguas", "se completa la tarea", "el usuario ve el dashboard", "la alarma se activa", "el cliente recibe el dato"],
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
            "template": "Un test tiene {n} preguntas. Cada pregunta correcta suma {p} puntos y cada incorrecta resta {q}. Si un estudiante responde todas y obtiene {score} puntos, ¿cuántas acertó? Resuelve con ecuaciones.",
            "variables": {
                "n": [20, 25, 30, 40, 50],
                "p": [4, 5, 3, 2, 1],
                "q": [1, 2, 1, 1, 0],
                "score": [70, 85, 60, 90, 45],
            },
            "difficulty": "medium",
            "answer": (
                "Sistema de ecuaciones:\n"
                "x + y = {n}\n"
                "{p}x - {q}y = {score}\n\n"
                "Resolución:\n"
                "y = {n} - x\n"
                "{p}x - {q}({n} - x) = {score}\n"
                "Despejar x = correctas, y = incorrectas.\n"
                "Verificación: x + y = {n} y puntaje coincide."
            ),
        },
        {
            "template": "Tres interruptores controlan una lámpara en otra habitación. Solo puedes entrar una vez. ¿Cómo determinar cuál interruptor enciende la lámpara? Explica la estrategia.",
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
            "template": "En una carrera, adelantas al segundo. ¿En qué posición terminas? Explica por qué mucha gente responde mal.",
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
            "template": "Un granjero tiene {n} animales entre {A} y {B}. Cuenta {legs} patas y {heads} cabezas. ¿Cuántos {A} y cuántos {B} hay? Resuelve el sistema.",
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
                "Sustituir y resolver para x e y.\n"
                "Verificación: x + y = {heads}."
            ),
        },
    ],
    "math": [
        {
            "template": "Calcula el límite de {expr} cuando {var} tiende a {val}. Muestra el desarrollo paso a paso.",
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
            "template": "Deriva {expr} respecto a {var}. Simplifica el resultado.",
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
            "template": "Un proyecto cuesta ${n} y se deprecia un {p}% anual. ¿Cuánto valdrá después de {t} años con depreciación compuesta?",
            "variables": {
                "n": [10000, 50000, 25000],
                "p": [10, 15, 20],
                "t": [3, 5, 10],
            },
            "difficulty": "easy",
            "answer": (
                "Fórmula: V = P * (1 - r)^t\n"
                "Paso 1: Convertir porcentaje a decimal: r = {p}/100 = {r_dec}.\n"
                "Paso 2: Aplicar fórmula de depreciación compuesta.\n"
                "Paso 3: Calcular resultado final.\n"
                "Paso 4: Interpretar en contexto económico."
            ),
        },
        {
            "template": "Calcula la probabilidad de obtener al menos un {A} en {n} lanzamientos de un dado justo de {s} caras.",
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
            "template": "Si f(x) = {expr}, encuentra el valor de x que maximiza f(x) en el intervalo [{a}, {b}]. Verifica que es un máximo.",
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
            "template": "Escribe una función en Python que {A}. Luego, optimízala para reducir su complejidad temporal. Explica los cambios.",
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
            "template": "Implementa un {A} en Python con las siguientes especificaciones: {B}. Incluye manejo de errores y tests unitarios básicos.",
            "variables": {
                "A": ["cache LRU", "árbol binario de búsqueda", "stack con operación min() O(1)", "sistema de colas con prioridad", "parser de JSON simple"],
                "B": [
                    "capacidad {n}, operaciones get/put en O(1)",
                    "inserción, búsqueda y eliminación en O(log n)",
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
            "template": "Planifica la implementación de {A} para un equipo de {n} desarrolladores con un plazo de {t} semanas. Considera riesgos, dependencias y entregables.",
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
                "Paso 5: Plan de contingencia para riesgos principales."
            ),
        },
        {
            "template": "Tienes {n} tareas con las siguientes duraciones y dependencias: {details}. Determina el camino crítico y la duración mínima del proyecto.",
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
                "Paso 1: Construir grafo de dependencias.\n"
                "Paso 2: Calcular earliest start/finish hacia adelante.\n"
                "Paso 3: Calcular latest start/finish hacia atrás.\n"
                "Paso 4: Holgura = LS - ES; camino crítico = nodos con holgura 0.\n"
                "Paso 5: Duración mínima = suma de duraciones en el camino crítico."
            ),
        },
        {
            "template": "Un servidor maneja {n} solicitudes por segundo con latencia media de {lat}ms. Si la carga aumenta un {p}%, ¿qué estrategias aplicarías para mantener el SLA de {sla}ms?",
            "variables": {
                "n": [1000, 5000, 10000],
                "lat": [50, 100, 200],
                "p": [50, 100, 200],
                "sla": [100, 150, 300],
            },
            "difficulty": "hard",
            "answer": (
                "Paso 1: Calcular nueva carga esperada: {n} * (1 + {p}/100) = {new_load} req/s.\n"
                "Paso 2: Identificar cuello de botella.\n"
                "Paso 3: Estrategias: escalado horizontal, caching agresivo, async/queues, connection pooling.\n"
                "Paso 4: Validar con load testing antes de producción."
            ),
        },
    ],
    "search": [
        {
            "template": "Formula una consulta de búsqueda avanzada en Google (operadores booleanos, comillas, site:, filetype:) para encontrar {A}. Explica cada parte de la query.",
            "variables": {
                "A": [
                    "presentaciones PDF sobre machine learning en salud",
                    "repositorios GitHub de código Python para scraping",
                    "artículos de investigación sobre LLMs pequeños",
                    "tutoriales de Docker para principiantes",
                    "datasets abiertos de imágenes médicas",
                ],
            },
            "difficulty": "easy",
            "answer": (
                "Query propuesta:\n"
                "  (machine learning OR \"ML\") AND salud filetype:pdf site:edu OR site:gov\n\n"
                "Desglose:\n"
                "- (machine learning OR \"ML\"): sinónimos y variantes.\n"
                "- AND salud: intersecta con dominio de aplicación.\n"
                "- filetype:pdf: filtra por tipo de documento.\n"
                "- site:edu OR site:gov: prioriza fuentes académicas/gobierno.\n\n"
                "Consejos: ajustar idioma, fecha y excluir términos irrelevantes con -palabra."
            ),
        },
        {
            "template": "Diseña una estrategia de búsqueda de información para investigar {A}. Define keywords, fuentes primarias, filtros de calidad y método de validación de hallazgos.",
            "variables": {
                "A": [
                    "la seguridad de contratos inteligentes en Ethereum",
                    "técnicas de compresión de modelos LLM",
                    "arquitecturas de microservicios para fintech",
                    "métodos de detección de sesgo en IA",
                    "optimización de bases de datos de series temporales",
                ],
            },
            "difficulty": "medium",
            "answer": (
                "Estrategia:\n"
                "1. Keywords: términos principales + sinónimos + variantes en inglés.\n"
                "2. Fuentes primarias: papers (arXiv, ACL Anthropy), documentación oficial, blogs de ingeniería.\n"
                "3. Filtros de calidad: peer-review, citas, fecha de publicación, autoridad del autor.\n"
                "4. Validación: cruzar al menos 3 fuentes independientes; buscar réplicas o refutaciones."
            ),
        },
        {
            "template": "Analiza los siguientes resultados de búsqueda para {query} y clasifícalos por relevancia, autoridad y actualidad. Identifica gaps en la información:\n\n{results}",
            "variables": {
                "query": ["Python async", "cybersecurity tools", "LLM fine-tuning", "cloud architecture"],
                "results": [
                    "\n1. Python Docs (docs.python.org) - Guía oficial sobre asyncio\n2. Blog personal (2020) - Introducción a async/await\n3. Stack Overflow - Pregunta sobre EventLoop\n4. Reddit r/Python - Discusión sobre performance\n5. Tutorial YouTube (2024) - Async avanzado con aiohttp\n",
                    "\n1. NIST Guide (2023) - Framework de ciberseguridad\n2. Blog corporativo - Top 10 herramientas\n3. GitHub Repo - Script de escaneo automatizado\n4. Wikipedia - Historia de la ciberseguridad\n5. Foro no verificado - 'Mejores tools 2021'\n",
                ],
            },
            "difficulty": "medium",
            "answer": (
                "Clasificación:\n"
                "- Alta autoridad + actual: docs.python.org, NIST Guide.\n"
                "- Media autoridad + actual: Stack Overflow, GitHub Repo, YouTube tutorial.\n"
                "- Baja autoridad o desactualizado: Blog personal 2020, foro no verificado.\n\n"
                "Gaps identificados:\n"
                "1. Falta contenido intermedio entre básico y avanzado.\n"
                "2. Poca cobertura de optimización de rendimiento.\n"
                "3. Ausencia de benchmarks comparativos entre herramientas.\n\n"
                "Recomendación: complementar con papers recientes y documentación oficial."
            ),
        },
    ],
    "analysis": [
        {
            "template": "Analiza el siguiente conjunto de datos y determina tendencias, valores atípicos y correlaciones:\n\n{dataset}",
            "variables": {
                "dataset": [
                    "Ventas mensuales: [120, 135, 128, 145, 160, 155, 170, 180, 175, 190, 210, 205]\nCostos mensuales: [80, 85, 82, 90, 95, 93, 100, 105, 102, 110, 115, 112]",
                    "Tiempos de respuesta API (ms): [45, 52, 48, 61, 55, 49, 120, 53, 47, 58, 62, 51, 50, 49]\nRequests por minuto: [200, 210, 205, 350, 220, 215, 380, 225, 210, 230, 240, 218, 212, 209]",
                    "Puntuaciones examen: [78, 85, 92, 65, 88, 72, 95, 81, 77, 69, 84, 91, 73, 86, 67, 89]\nHoras de estudio: [10, 12, 15, 8, 13, 9, 16, 11, 10, 7, 12, 14, 9, 13, 8, 11]",
                ]
            },
            "difficulty": "medium",
            "answer": (
                "Análisis estadístico:\n"
                "1. Limpiar datos: verificar valores atípicos (outliers) con IQR o z-score.\n"
                "2. Calcular estadísticas descriptivas: media, mediana, desviación estándar.\n"
                "3. Visualizar: scatter plot para correlación, histograma para distribución.\n"
                "4. Calcular coeficiente de correlación (Pearson/Spearman).\n"
                "5. Interpretar: tendencia creciente/decreciente, estacionalidad, relación causal vs correlación."
            ),
        },
        {
            "template": "Un sistema tiene los siguientes logs de eventos. Identifica el patrón de fallo y propone una solución:\n\n{logs}",
            "variables": {
                "logs": [
                    "[10:00] OK - Latencia 45ms\n[10:01] OK - Latencia 52ms\n[10:02] WARN - Latencia 150ms\n[10:03] ERROR - Timeout 5000ms\n[10:04] ERROR - Timeout 5000ms\n[10:05] OK - Latencia 48ms",
                    "[Mon] CPU 45%, RAM 60%\n[Tue] CPU 78%, RAM 82%\n[Wed] CPU 92%, RAM 91%\n[Thu] CPU 88%, RAM 89%\n[Fri] CPU 70%, RAM 75%",
                ]
            },
            "difficulty": "medium",
            "answer": (
                "Patrón detectado:\n"
                "- Picos de carga en horarios específicos (10:02-10:04).\n"
                "- Recursos escalan con días de la semana (Wed peak).\n\n"
                "Hipótesis:\n"
                "1. Pico de tráfico en horario laboral.\n"
                "2. Memory leak acumulativo que se recupera con restart.\n\n"
                "Solución:\n"
                "- Implementar auto-scaling basado en métricas.\n"
                "- Revisar queries N+1 y conexiones sin cierre.\n"
                "- Agregar circuit breaker y timeout tuning.\n"
                "- Monitorear con APM (New Relic, Datadog)."
            ),
        },
    ],
    "synthesis": [
        {
            "template": "Diseña una arquitectura de software para {A} que escale hasta {n} usuarios. Considera {B} y {C}. Describe los componentes principales y sus interacciones.",
            "variables": {
                "A": ["una red social de mensajería", "un sistema de pagos", "un servicio de streaming", "una plataforma de e-learning"],
                "n": ["1 millón", "10 millones", "100 millones", "500 mil"],
                "B": ["alta disponibilidad", "baja latencia", "seguridad de datos", "costos operativos"],
                "C": ["monitoreo continuo", "despliegue continuo", "tolerancia a fallos", "cumplimiento normativo"],
            },
            "difficulty": "expert",
            "answer": (
                "Arquitectura propuesta:\n"
                "1. Capa de presentación: CDN + edge caching + SPA.\n"
                "2. API Gateway: rate limiting, auth, routing, observabilidad.\n"
                "3. Servicios core: microservicios independientes por dominio.\n"
                "4. Datos: DB primaria (PostgreSQL), cache (Redis), colas (Kafka), búsqueda (Elasticsearch).\n"
                "5. Infra: Kubernetes + auto-scaling + multi-AZ.\n\n"
                "Consideraciones {B} y {C}:\n"
                "- {B}: replicación, failover, health checks.\n"
                "- {C}: logging estructurado, tracing distribuido, alertas inteligentes."
            ),
        },
        {
            "template": "Integra {A} y {B} en un sistema unificado. Define la API de comunicación, el formato de datos y el flujo de control.",
            "variables": {
                "A": ["un modelo de IA local", "un servicio de búsqueda web", "una base de datos vectorial", "un cola de mensajes"],
                "B": ["una interfaz de chat", "un dashboard de analíticas", "un pipeline ETL", "un sistema de notificaciones"],
            },
            "difficulty": "hard",
            "answer": (
                "Diseño de integración:\n"
                "1. API REST/GraphQL entre {A} y {B}.\n"
                "2. Formato de datos: JSON con schema validation (Pydantic).\n"
                "3. Flujo de control:\n"
                "   - Request → {B} → validación → {A} → proceso → respuesta → {B}.\n"
                "   - Eventos asíncronos para operaciones largas.\n"
                "4. Manejo de errores: retries, dead-letter queue, circuit breaker.\n"
                "5. Observabilidad: logs, métricas, trazas distribuidas."
            ),
        },
    ],
}


class TaskSimulationEngine:
    """Genera tareas simuladas avanzadas para entrenamiento."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()

    def _generate_key(self, category: str, template_idx: int, difficulty: str) -> str:
        return f"{category}:{template_idx}:{difficulty}"

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

    def generate_task(self, category: str, difficulty: Optional[str] = None) -> Dict:
        templates = TASK_TEMPLATES.get(category, [])
        if not templates:
            raise ValueError(f"Unknown category: {category}")

        if difficulty is None:
            difficulty = random.choice(DIFFICULTY_LEVELS)

        eligible = [t for t in templates if t.get("difficulty", "medium") == difficulty]
        if not eligible:
            eligible = templates

        template = random.choice(eligible)
        question = self._fill_template(template["template"], template.get("variables", {}))

        key = self._generate_key(category, templates.index(template), difficulty)
        if key in self.generated_keys:
            return self.generate_task(category, difficulty)
        self.generated_keys.add(key)

        raw_answer = template.get("answer", "Respuesta estructurada para la categoría solicitada.")
        answer = self._fill_template(raw_answer, template.get("variables", {}))

        return {
            "text": question,
            "output": answer,
            "metadata": {
                "source": "task_simulation",
                "category": category,
                "difficulty": difficulty,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate_batch(
        self,
        count: int = 50,
        categories: Optional[List[str]] = None,
        difficulty: Optional[str] = None,
    ) -> List[Dict]:
        if categories is None:
            categories = list(TASK_TEMPLATES.keys())

        results = []
        per_cat = max(1, count // len(categories))
        for cat in categories:
            for _ in range(per_cat):
                try:
                    results.append(self.generate_task(cat, difficulty))
                except Exception as exc:
                    logger.debug(f"Skip task {cat}: {exc}")
        return results[:count]

    def save_to_jsonl(self, tasks: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(tasks)} tasks -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    engine = TaskSimulationEngine(seed=42)
    categories = args.categories.split(",") if args.categories else None
    tasks = engine.generate_batch(
        count=args.count,
        categories=categories,
        difficulty=args.difficulty,
    )
    output = Path(args.output)
    engine.save_to_jsonl(tasks, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Task Simulation Engine")
    p.add_argument("--count", type=int, default=50, help="Número de tareas a generar")
    p.add_argument("--categories", type=str, default=None, help="Categorías separadas por coma")
    p.add_argument("--difficulty", type=str, default=None, choices=DIFFICULTY_LEVELS)
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
