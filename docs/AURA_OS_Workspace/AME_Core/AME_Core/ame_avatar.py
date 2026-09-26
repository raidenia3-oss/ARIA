"""
Avatar de texto estilo anime para AME Agent en terminal.
Muestra una chica anime ASCII mientras responde.
"""

import random

AVATAR_FRAMES = [
    """
     ╭──────────────╮
     │  (◕‿◕✿)     │
     │  AME AGENT   │
     │  ▓▓▓▓░░░░░░ │
     ╰──────────────╯""",
    """
     ╭──────────────╮
     │  (｡◕‿◕｡)   │
     │  PROCESANDO  │
     │  ▓▓▓▓▓▓░░░░ │
     ╰──────────────╯""",
    """
     ╭──────────────╮
     │  (ﾉ◕ヮ◕)ﾉ   │
     │  LISTO!      │
     │  ▓▓▓▓▓▓▓▓▓▓ │
     ╰──────────────╯""",
]

THINKING_LINES = [
    "Analizando solicitud...",
    "Consultando base de conocimiento...",
    "Procesando con HF Space...",
    "Generando respuesta...",
]


class AMEAvatar:
    def show_thinking(self):
        import sys, time

        frame = AVATAR_FRAMES[1]
        thought = random.choice(THINKING_LINES)
        print(f"\033[96m{frame}\033[0m")
        print(f"\033[93m  ► {thought}\033[0m")

    def show_response(self, text: str):
        frame = AVATAR_FRAMES[2]
        print(f"\033[96m{frame}\033[0m")
        print(f"\033[97m{text}\033[0m")

    def show_idle(self):
        frame = AVATAR_FRAMES[0]
        print(f"\033[96m{frame}\033[0m")
        print("\033[90m  Esperando órdenes...\033[0m")


if __name__ == "__main__":
    avatar = AMEAvatar()
    avatar.show_thinking()
    import time

    time.sleep(2)
    avatar.show_response("Hola, soy AME Agent. ¿En qué puedo ayudarte?")
