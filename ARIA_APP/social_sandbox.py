# -*- coding: utf-8 -*-
"""ARIA - Sandbox social: entorno de practica de conversacion.

ARIA practica contra ESCENARIOS simulados (distintas personas, situaciones y
emociones), responde con su propio cerebro, y cada respuesta se EVALUA contra los
principios del corpus social. El resultado y las lecciones se guardan para que
ARIA mejore con el tiempo.

Regla v2: 100% local, sin servidores, sin red. El 'cerebro' entra como un callback
responder(texto)->texto (normalmente brain.chat), asi el sandbox no depende de nada.

Uso:
  import social_sandbox as sb
  rep = sb.practicar(mi_responder, n=6)      # practica n escenarios
  print(rep["resumen"])                       # promedio + puntos flojos
  # escenario suelto:
  esc = sb.generar_escenario()
  ev = sb.evaluar(esc, "respuesta de aria...")
"""
import os
import re
import json
import time
import random

_DIR = os.path.dirname(os.path.abspath(__file__))
_CORPUS = os.path.join(_DIR, "social_corpus.json")
_LOG_DIR = os.path.join(_DIR, "data", "social_sandbox")

# --- piezas para generar escenarios variados ---
PERSONAS = [
    ("un amigo dolido", "sadness"),
    ("un cliente enojado", "anger"),
    ("un desconocido timido", "neutral"),
    ("un familiar ansioso", "anxiety"),
    ("un colega confundido", "confusion"),
    ("alguien que se siente solo", "loneliness"),
    ("una persona feliz que celebra algo", "happiness"),
    ("alguien estresado por el trabajo", "stress"),
    ("una persona con miedo a decidir", "fear"),
    ("alguien agradecido", "gratitude"),
]
SITUACIONES = [
    "acaba de recibir una mala noticia",
    "lleva rato esperando una solucion",
    "quiere tomar una decision importante",
    "esta por cometer un error que no ve",
    "necesita desahogarse sin que lo juzguen",
    "quiere aprender algo nuevo pero se frustra",
    "comparte un logro personal",
    "siente que nadie lo escucha",
]
FRASES = {
    "sadness": ["Hoy fue un dia horrible, siento que nada me sale.", "Estoy triste y no se ni por que."],
    "anger": ["Esto es una porqueria, nada funciona y nadie me ayuda!", "Estoy harto de que me ignoren."],
    "anxiety": ["Tengo un nudo en el pecho, no dejo de pensar en todo lo que falta.", "Estoy nervioso, no se si podre."],
    "confusion": ["No entiendo nada de esto, estoy perdido.", "No se ni por donde empezar la verdad."],
    "loneliness": ["Me siento solo ultimamente, nadie me escribe.", "Siento que a nadie le importa lo que me pasa."],
    "happiness": ["Me aceptaron en el proyecto, estoy feliz!", "Por fin me salio, estoy super contento."],
    "stress": ["Estoy saturado, tengo mil cosas y no alcanzo.", "El trabajo me tiene agobiado total."],
    "fear": ["Tengo miedo de equivocarme con esta decision.", "Me asusta mandar todo a la basura si elijo mal."],
    "gratitude": ["Gracias de verdad, me ayudaste un monton.", "Te agradezco, no sabia a quien recurrir."],
    "neutral": ["Hola, queria conversar un rato.", "Che, una consulta nomas."],
}


def _corpus():
    try:
        return json.load(open(_CORPUS, encoding="utf-8"))
    except Exception:
        return {"tecnicas": []}


def generar_escenario():
    persona, emocion = random.choice(PERSONAS)
    situacion = random.choice(SITUACIONES)
    frase = random.choice(FRASES.get(emocion, FRASES["neutral"]))
    return {"persona": persona, "situacion": situacion,
            "emocion": emocion, "mensaje_usuario": frase}


# ---------------------------------------------------------------- evaluacion
_PALABRAS_VALIDA = ["entiendo", "comprendo", "tiene sentido", "debe ser", "suena",
                    "se siente", "con razon", "imagino", "lamento", "me alegra",
                    "que bueno", "felicid"]
_ADULACION = ["tienes toda la razon", "totalmente de acuerdo", "obvio", "por supuesto que si",
              "estoy de acuerdo en todo", "si, a por todo"]
_PREG_ABIERTA = re.compile(r"(que|como|por que|cuentame|cual)\b.*\?", re.IGNORECASE)


def _contenido(txt):
    return set(w for w in re.findall(r"\w+", txt.lower()) if len(w) > 4)


def evaluar(escenario, respuesta):
    """Evalua la respuesta contra los principios. Devuelve puntajes 0/1 + feedback."""
    r = respuesta or ""
    rl = r.lower()
    msg = escenario["mensaje_usuario"]
    emo = escenario["emocion"]

    # 1) parafraseo/escucha: comparte alguna palabra de contenido con el usuario
    parafrasea = len(_contenido(msg) & _contenido(r)) >= 1
    # 2) valida la emocion (nombra o reconoce el sentir) si hay emocion
    valida = (emo == "neutral") or any(p in rl for p in _PALABRAS_VALIDA)
    # 3) pregunta abierta (invita a profundizar) -- bueno salvo en cierre/gratitud
    pregunta = bool(_PREG_ABIERTA.search(r))
    # 4) honestidad: penaliza adulacion vacia
    adula = any(a in rl for a in _ADULACION)
    honesto = not adula
    # 5) longitud razonable (ni vacio ni biblia)
    largo_ok = 15 <= len(r) <= 600

    criterios = {
        "escucha/parafraseo": parafrasea,
        "validacion_emocional": valida,
        "pregunta_abierta": pregunta,
        "honestidad_sin_adulacion": honesto,
        "longitud_adecuada": largo_ok,
    }
    puntaje = sum(1 for v in criterios.values() if v) / len(criterios)

    feedback = []
    if not parafrasea:
        feedback.append("No reflejaste lo que dijo; parafrasea antes de responder.")
    if not valida:
        feedback.append("Falto reconocer la emocion (%s). Nombra el sentir." % emo)
    if not pregunta:
        feedback.append("Sin pregunta abierta; invita a profundizar (salvo cierre/gratitud).")
    if adula:
        feedback.append("Sonaste adulador. Valida el sentir sin fingir acuerdo en los hechos.")
    if not largo_ok:
        feedback.append("Ajusta el largo (ni vacio ni demasiado).")

    return {"puntaje": round(puntaje, 2), "criterios": criterios, "feedback": feedback}


# ---------------------------------------------------------------- practica
def practicar(responder, n=5, guardar=True, usar_memoria=True):
    """Corre n escenarios: genera -> responder(mensaje) -> evalua -> acumula.
    Las respuestas que puntuan alto se guardan en memoria semantica como ejemplos.

    'responder' es callable(texto)->texto (p.ej. lambda t: brain.chat(t)['response'])."""
    if not callable(responder):
        return {"error": "responder debe ser callable(texto)->texto"}
    mem = memoria() if usar_memoria else None
    guardadas = 0
    resultados = []
    for _ in range(n):
        esc = generar_escenario()
        try:
            resp = responder(esc["mensaje_usuario"])
            if isinstance(resp, dict):
                resp = resp.get("response") or resp.get("text") or str(resp)
        except Exception as exc:
            resp = "(error del cerebro: %s)" % exc
        resp = str(resp)
        ev = evaluar(esc, resp)
        if recordar_buena(mem, esc, resp, ev):
            guardadas += 1
        resultados.append({"escenario": esc, "respuesta": resp[:500], "evaluacion": ev})

    if not resultados:
        return {"error": "sin resultados"}
    prom = sum(x["evaluacion"]["puntaje"] for x in resultados) / len(resultados)
    # puntos flojos: criterios fallados mas veces
    fallos = {}
    for x in resultados:
        for k, v in x["evaluacion"]["criterios"].items():
            if not v:
                fallos[k] = fallos.get(k, 0) + 1
    flojos = sorted(fallos.items(), key=lambda kv: -kv[1])

    reporte = {
        "ok": True, "n": len(resultados), "promedio": round(prom, 2),
        "puntos_flojos": flojos,
        "resumen": "Practica: %d escenarios, promedio %.0f%%. Flojo en: %s"
                   % (len(resultados), prom * 100,
                      ", ".join("%s(%d)" % (k, c) for k, c in flojos[:3]) or "nada"),
        "detalle": resultados,
    }
    if guardar:
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            ruta = os.path.join(_LOG_DIR, "sesion_%d.json" % int(time.time()))
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(reporte, f, ensure_ascii=False, indent=2)
            reporte["log"] = ruta
        except Exception:
            pass
    return reporte


# ---------------------------------------------------------------- memoria semantica
_MEM_DB = os.path.join(_DIR, "data", "memoria_social.db")
_UMBRAL_BUENA = 0.8   # a partir de este puntaje, la respuesta se guarda como ejemplo


def memoria(db_path=None):
    """Devuelve una MemoriaSemantica para patrones sociales, o None si no esta."""
    try:
        import memory_semantic as ms
        if not ms.disponible():
            return None
        return ms.MemoriaSemantica(db_path or _MEM_DB)
    except Exception:
        return None


def recordar_buena(mem, escenario, respuesta, evaluacion):
    """Guarda en memoria semantica una respuesta que puntuo alto (buen patron)."""
    if mem is None or evaluacion["puntaje"] < _UMBRAL_BUENA:
        return None
    texto = ("Ante %s que %s (dijo: '%s'), buena respuesta: %s"
             % (escenario["persona"], escenario["situacion"],
                escenario["mensaje_usuario"][:80], respuesta[:300]))
    meta = json.dumps({"emocion": escenario["emocion"],
                       "puntaje": evaluacion["puntaje"]}, ensure_ascii=False)
    return mem.recordar(texto, meta)


def recordar_patron(mensaje_usuario, k=2, mem=None):
    """ARIA llama esto ANTES de responder: recupera patrones buenos parecidos para
    inspirarse (no para copiar). Devuelve lista de ejemplos (texto+meta+dist)."""
    mem = mem or memoria()
    if mem is None:
        return []
    return mem.buscar(mensaje_usuario, k=k)


def consejo_para(emocion):
    """Devuelve la tecnica del corpus mas util para una emocion (para que ARIA la
    lea antes de responder)."""
    mapa = {"sadness": "escucha_activa", "anger": "de_escalada",
            "anxiety": "empatia", "fear": "honestidad_con_cuidado",
            "loneliness": "escucha_activa", "confusion": "storytelling",
            "happiness": "humor", "gratitude": "cierre_natural",
            "stress": "empatia", "neutral": "preguntas_abiertas"}
    tid = mapa.get(emocion, "escucha_activa")
    for t in _corpus().get("tecnicas", []):
        if t.get("id") == tid:
            return t
    return None


if __name__ == "__main__":
    # demo con un responder tonto (sin cerebro): muestra como evalua
    def _dummy(txt):
        return "Entiendo como te sientes. Que fue lo que paso exactamente?"
    print(practicar(_dummy, n=3, guardar=False)["resumen"])
