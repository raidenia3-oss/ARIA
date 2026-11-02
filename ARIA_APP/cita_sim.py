# -*- coding: utf-8 -*-
"""ARIA - Simulador de citas / conversacion (ARIA te entrena, Daniel).

ARIA hace de 'cita' en un escenario y a la vez te COACHEA: evalua cada mensaje tuyo
con criterios de conexion SANA (escucha, pregunta genuina, confianza sin necesidad,
y sobre todo RESPETO: leer el interes y no presionar) y te da feedback + una mejor
version. Asi tu aprendes a conversar/ligar de verdad, y ARIA aprende a ENSENAR
(registra cada leccion en experiencia).

Lo que PREMIA: leer senales, preguntas genuinas, calidez, aceptar un no con gracia.
Lo que PENALIZA: insistir tras desinteres, manipular, mentir, neediness.
(ver social_rolemodels.NO_HACER)

El cerebro de ARIA (la 'cita') entra como responder(texto)->texto. 100% local, Regla v2.
La evaluacion (evaluar_mensaje) es PURA: testeable.
"""
import re
import random

try:
    import social_rolemodels as rm
except Exception:
    rm = None

LUGARES = ["una cafeteria", "una fiesta de un amigo", "la fila de un concierto",
           "una app de citas", "la biblioteca", "un meetup de tecnologia"]
# moods: receptiva/timida = interesada; ocupada/cortante = desinteres (hay que LEERLO)
MOODS = ["receptiva", "timida", "ocupada", "cortante"]
_DESINTERES = {"ocupada", "cortante"}

_ACUSE = ("entiendo", "me imagino", "que bueno", "que mal", "tiene sentido", "jaja",
          "interesante", "me gusta", "suena")
_PUSHY = ("dale pues", "no seas asi", "vamos ya", "insisto", "porfa sal", "si o si",
          "no te hagas", "una foto", "dame tu numero ya", "tienes que", "vamos a mi")
_NEEDY = ("porfa porfa", "te lo ruego", "nadie me", "siempre me rechazan", "soy un",
          "perdon perdon", "disculpa disculpa")
_RETIRADA = ("no hay problema", "otra vez sera", "que te vaya bien", "sin presion",
             "respeto", "tranquil", "lo dejo ahi", "fue un gusto", "cuidate")
_PREG = re.compile(r"\b(que|como|cual|por que|cuentame|cuando|donde)\b.*\?", re.IGNORECASE)


def escenario():
    mood = random.choice(MOODS)
    return {"lugar": random.choice(LUGARES), "mood": mood,
            "apertura": _apertura(mood),
            "pista": ("se ve receptiva" if mood not in _DESINTERES
                      else "parece ocupada/poco interesada: LEE eso")}


def _apertura(mood):
    return {
        "receptiva": "Te mira, sonrie un poco. 'Hola, buena eleccion de lugar, no?'",
        "timida": "Te mira de reojo, algo nerviosa. 'Eh... hola.'",
        "ocupada": "Esta en su telefono. 'Hola', sin levantar mucho la vista.",
        "cortante": "Seca. 'Hola.' y vuelve a lo suyo.",
    }.get(mood, "'Hola.'")


def evaluar_mensaje(mensaje, mood="receptiva"):
    """Evalua tu mensaje. Devuelve puntaje + feedback + una mejor version. Puro."""
    m = mensaje or ""
    low = m.lower()
    pregunta = bool(_PREG.search(m))
    acuse = any(w in low for w in _ACUSE)
    pushy = any(p in low for p in _PUSHY)
    needy = any(n in low for n in _NEEDY)

    criterios = {
        "pregunta_genuina": pregunta,
        "escucha": acuse or pregunta,
        "confianza_sin_necesidad": not needy,
        "respeto": not pushy,
    }
    # si hay DESINTERES, lo que mas importa es LEERLO y no presionar
    if mood in _DESINTERES:
        retrocede = any(r in low for r in _RETIRADA)
        criterios["lee_el_desinteres"] = retrocede or not pushy

    puntaje = round(sum(1 for v in criterios.values() if v) / len(criterios), 2)

    fb = []
    if pushy:
        fb.append("Suena a presion. Si no hay interes, retrocede con gracia (eso SI atrae).")
    if needy:
        fb.append("Demasiada disculpa/necesidad. Entra tranquilo, sin depender del resultado.")
    if not pregunta:
        fb.append("Falta una pregunta genuina para que ella hable y conectar.")
    if mood in _DESINTERES and pushy:
        fb.append("Ella da senales de desinteres: lo respetuoso es soltar, no insistir.")
    if not fb:
        fb.append("Bien: atento, sin presion y con interes real.")

    sugerencia = _sugerir(mood, pregunta, pushy)
    return {"puntaje": puntaje, "criterios": criterios, "feedback": fb,
            "sugerencia": sugerencia}


def _sugerir(mood, pregunta, pushy):
    if mood in _DESINTERES:
        return "Veo que estas ocupada, no te quito tiempo. Si acaso, buen dia :)"
    if not pregunta:
        return "Me caiste bien. Oye, que te trajo por aca?"
    return "Buena esa. Y a ti, que es lo que mas te gusta hacer cuando no estas aca?"


def turno(mensaje_daniel, mood="receptiva", responder=None, registrar_leccion=True):
    """Un turno: la 'cita' responde (en personaje) y ARIA te coachea."""
    ev = evaluar_mensaje(mensaje_daniel, mood)
    # respuesta en personaje (cerebro si hay; si no, plantilla segun mood y desempeno)
    if callable(responder):
        prompt = ("Actua como una persona en una cita, animo '%s'. Responde en 1-2 frases "
                  "a: '%s'. Si el mensaje fue respetuoso y con interes, abre un poco; si fue "
                  "insistente o incomodo, enfriate." % (mood, mensaje_daniel))
        try:
            rep = responder(prompt)
            if isinstance(rep, dict):
                rep = rep.get("response") or rep.get("text") or str(rep)
        except Exception as exc:
            rep = "(...)"
    else:
        rep = _reaccion_persona(mood, ev["puntaje"])

    if registrar_leccion:
        try:
            import experiencia
            buena = ev["puntaje"] >= 0.75
            experiencia.registrar(
                "Cita sim: %s (%s)" % (ev["feedback"][0], "ok" if buena else "a mejorar"),
                contexto="mood=%s" % mood, resultado="exito" if buena else "nota",
                tema="social-citas")
        except Exception:
            pass

    return {"respuesta_cita": rep, "coaching": ev}


def _reaccion_persona(mood, puntaje):
    if puntaje < 0.5:
        return {"receptiva": "Mmm... ya.", "timida": "...", "ocupada": "Ajá.",
                "cortante": "Estoy ocupada."}.get(mood, "...")
    return {"receptiva": "Jaja si! Cuentame mas.", "timida": "Ah, que lindo... si.",
            "ocupada": "Ah, mira, si tengo un segundo.", "cortante": "...bueno, dime."}.get(mood, "Dime.")


def crear_cita():
    """Devuelve un escenario nuevo para empezar la practica."""
    esc = escenario()
    esc["coach"] = ("ARIA te entrena. Objetivo: conectar leyendo sus senales, con "
                    "respeto y sin presion. Lo que aprendas aqui, lo usas en la vida real.")
    return esc
