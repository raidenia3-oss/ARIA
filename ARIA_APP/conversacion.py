# -*- coding: utf-8 -*-
"""ARIA - Estado de conversacion (continuidad y tono entre turnos).

La capa social vieja miraba cada mensaje SUELTO. Esto le da MEMORIA de la charla:
como viene el animo del usuario a lo largo de los turnos (mejora/empeora), en que
REGISTRO habla (para espejarlo), de que se esta hablando y que tan enganchado esta.
ARIA pide contexto() antes de responder para sonar continua ('vienes cargado hace
rato', 'te noto mas animado') y adaptar el tono.

Usa social_skills para leer cada turno. 100% local, Regla v2. La logica de tendencia
es pura y testeable.
"""
from collections import deque

try:
    import social_skills as ss
except Exception:
    ss = None

_NEG = {"sadness", "anger", "anxiety", "fear", "loneliness", "stress"}
_POS = {"happiness", "gratitude"}


def _valencia(emocion, inten):
    """Emocion+intensidad -> valencia con signo (-1..1). Negativa pesa negativo."""
    if emocion in _NEG:
        return -max(0.3, inten)
    if emocion in _POS:
        return max(0.3, inten)
    return 0.0


def _tendencia(valencias):
    """Lista de valencias (viejo->nuevo) -> 'mejora' | 'empeora' | 'estable'."""
    if len(valencias) < 2:
        return "estable"
    n = len(valencias)
    mitad = max(1, n // 2)
    viejo = sum(valencias[:mitad]) / mitad
    nuevo = sum(valencias[mitad:]) / (n - mitad)
    if nuevo - viejo > 0.25:
        return "mejora"
    if nuevo - viejo < -0.25:
        return "empeora"
    return "estable"


class Conversacion:
    def __init__(self, ventana=6):
        self.turnos = deque(maxlen=ventana)
        self.n_total = 0

    def registrar(self, texto_usuario):
        """Analiza un turno del usuario y lo guarda. Devuelve el analisis."""
        if ss is not None:
            a = ss.social_analysis(texto_usuario)
        else:
            a = {"emotion": "neutral", "emotions": [], "intensidad": 0.0, "registro": "formal"}
        turno = {
            "emocion": a["emotion"],
            "intensidad": a.get("intensidad", 0.0),
            "registro": a.get("registro", "formal"),
            "largo": len((texto_usuario or "").split()),
            "pregunta": "?" in (texto_usuario or ""),
        }
        self.turnos.append(turno)
        self.n_total += 1
        return a

    # ---------------------------------------------------------- lecturas
    def emocion_dominante(self):
        cuenta = {}
        for t in self.turnos:
            if t["emocion"] != "neutral":
                cuenta[t["emocion"]] = cuenta.get(t["emocion"], 0) + 1
        if not cuenta:
            return "neutral"
        return max(cuenta.items(), key=lambda kv: kv[1])[0]

    def tendencia(self):
        return _tendencia([_valencia(t["emocion"], t["intensidad"]) for t in self.turnos])

    def registro(self):
        casual = sum(1 for t in self.turnos if t["registro"] == "casual")
        return "casual" if casual * 2 >= len(self.turnos) and self.turnos else "formal"

    def enganche(self):
        """Engagement aprox: largo promedio de los mensajes del usuario."""
        if not self.turnos:
            return 0.0
        return round(sum(t["largo"] for t in self.turnos) / len(self.turnos), 1)

    def contexto(self):
        """Resumen que ARIA inyecta como guia ANTES de responder."""
        dom = self.emocion_dominante()
        ten = self.tendencia()
        reg = self.registro()
        guia = []
        if dom != "neutral":
            guia.append("el usuario viene con %s" % dom)
            if ten == "empeora":
                guia.append("y va a peor: reconocelo y baja el ritmo")
            elif ten == "mejora":
                guia.append("y va mejorando: acompana el cambio")
        guia.append("habla en registro %s: espejalo" % reg)
        return {
            "emocion_dominante": dom,
            "tendencia": ten,
            "registro": reg,
            "turnos": self.n_total,
            "enganche": self.enganche(),
            "guia": ". ".join(guia) + ".",
        }


def crear_conversacion(ventana=6):
    return Conversacion(ventana)
