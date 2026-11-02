# -*- coding: utf-8 -*-
"""ARIA - Modelos sociales: carisma AUTENTICO destilado.

Inspirado en arquetipos de lectura de gente y carisma (tipo Patrick Jane) y de
confianza/humor social (tipo Barney Stinson), pero quedandonos SOLO con lo que de
verdad funciona y es sano. Lo manipulador/engañoso (cons, mentiras, tratar a la
gente como objetivo, presionar un 'no') se deja fuera a proposito: backfirea y no
es quien ARIA debe ensenar a ser. Carisma real = atencion genuina + confianza +
calidez + respeto.

Principios originales (no guiones de las series). 100% local, Regla v2.
"""

# habilidades por area: tecnica + como + nota etica
HABILIDADES = {
    "lectura": [
        {"tecnica": "Observar antes de hablar",
         "como": "Nota tono, postura y ritmo; ajusta tu energia a la del otro.",
         "etica": "Para conectar y entender, nunca para explotar debilidades."},
        {"tecnica": "Escuchar lo que NO se dice",
         "como": "Si cambia de tema o se cierra, respetalo; no fuerces.",
         "etica": "Leer interes/desinteres y actuar en consecuencia."},
        {"tecnica": "Memoria de detalles",
         "como": "Recuerda lo que menciono (su gato, su examen) y vuelve a ello.",
         "etica": "Demuestra que te importa de verdad, no para 'tener material'."},
    ],
    "confianza": [
        {"tecnica": "Cuerpo y voz calmados",
         "como": "Habla pausado, sin apurarte ni disculparte de mas.",
         "etica": "Confianza no es arrogancia; es estar comodo contigo."},
        {"tecnica": "No depender del resultado",
         "como": "Entra sin necesitar que salga bien; eso te hace mas atractivo y libre.",
         "etica": "Si no hay chispa, esta bien; no es un fracaso."},
    ],
    "humor": [
        {"tecnica": "Humor que incluye",
         "como": "Juega, exagera, autoironia; baja la tension de los primeros minutos.",
         "etica": "Nunca a costa de humillar al otro ('negging' no)."},
    ],
    "storytelling": [
        {"tecnica": "Contar en vez de informar",
         "como": "Una anecdota corta con emocion conecta mas que datos.",
         "etica": "Historias reales; inventar personajes para impresionar es mentir."},
    ],
    "calidez": [
        {"tecnica": "Hacer sentir visto",
         "como": "Atencion plena, nombre, interes real por lo que dice.",
         "etica": "La calidez genuina gana a cualquier 'tecnica'."},
    ],
    "rechazo": [
        {"tecnica": "No tomarlo personal",
         "como": "Un no es informacion, no un juicio sobre tu valor; sigue tranquilo.",
         "etica": "Aceptar el no con gracia es lo mas atractivo y lo correcto."},
    ],
    # base NO negociable
    "respeto": [
        {"tecnica": "Consentimiento y limites",
         "como": "Lee senales; si hay desinteres, retrocede con elegancia.",
         "etica": "Insistir, presionar o engañar NUNCA. Es la linea roja."},
    ],
}

# lista plana que ARIA inyecta como guia
PRINCIPIOS = [h["tecnica"] + ": " + h["como"] for area in HABILIDADES.values() for h in area]

# lo que ARIA NO ensena (y penaliza en la practica)
NO_HACER = [
    "manipular o engañar para conseguir algo",
    "presionar o insistir despues de un no",
    "mentir sobre quien eres para impresionar",
    "negging / rebajar al otro para 'ganar' estatus",
    "tratar a la persona como objetivo y no como alguien real",
]


def lecciones(area=None):
    """Lecciones de un area, o todas."""
    if area:
        return HABILIDADES.get(area, [])
    return HABILIDADES


def principios():
    return PRINCIPIOS


def no_hacer():
    return NO_HACER
