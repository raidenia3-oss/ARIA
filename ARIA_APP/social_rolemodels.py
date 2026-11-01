# -*- coding: utf-8 -*-
"""ARIA - Modelos sociales: Patrick Jane y Barney Stinson (lecciones destiladas)."""
LECCIONES = {
    "patrick_jane": [
        "Observar micro-expresiones y contradicciones antes de hablar.",
        "Usar cold reading solo para empatizar, no para manipular.",
        "Hacer preguntas abiertas y dejar que el otro revele.",
        "Memoria de detalles (loci) para recordar preferencias.",
        "Validar antes de desafiar; suavizar verdades duras.",
    ],
    "barney_stinson": [
        "Confianza corporal y voz clara aumentan presencia social.",
        "Humor y juego reducen tension en primeras interacciones.",
        "Persistencia respetuosa puede convertir un no inicial en si.",
        "No usar manipulacion egoista; aprender de sus errores.",
        "La autenticidad final (Robin) vence a la mascara.",
    ],
}


def simulacion_citas(mensaje_usuario):
    return {
        "escenario": "cita simulada con Daniel",
        "guia": "ARIA ensena: escucha activa, validacion, humor, limites.",
        "respuesta": "Entiendo. Que te gustaria practicar hoy: apertura, conversacion profunda o cierre?",
    }


VIDEOS = {
    "patrick_jane": ["Patrick Jane cold reading The Mentalist", "Patrick Jane manipulation psychology"],
    "barney_stinson": ["Barney Stinson Playbook HIMYM", "Barney Stinson confidence flirting"],
}

def videos_referencia(personaje):
    return VIDEOS.get(personaje, [])

def investigar_personaje(personaje):
    return {"personaje": personaje, "videos": videos_referencia(personaje),
            "lecciones": LECCIONES.get(personaje, [])}
