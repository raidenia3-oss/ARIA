"""
Agente de voz para AURA.
Escucha comandos y los ejecuta en el ecosistema.
"""

import speech_recognition as sr
import requests
import os

HF_URL = "https://raiden456-slut.hf.space/v1/chat/completions"

AURA_COMMANDS = {
    "rollercoin": "scripts/start_rollercoin_auto.py",
    "estado": None,
    "buscar": None,
    "godot": None,
}


class VoiceAgent:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        self.running = False

    def listen(self) -> str | None:
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("Escuchando...")
            try:
                audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio, language="es-ES")
                print(f"Escuchado: {text}")
                return text.lower()
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except Exception as e:
                print(f"Error de voz: {e}")
                return None

    def process_command(self, text: str) -> str:
        if "rollercoin" in text and "iniciar" in text:
            import subprocess, sys

            subprocess.Popen(
                [
                    sys.executable,
                    "scripts/start_rollercoin_auto.py",
                ]
            )
            return "Iniciando RollerCoin bot"

        try:
            r = requests.post(
                HF_URL,
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "Eres AME, asistente de AURA. Responde brevemente en español.",
                        },
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 200,
                },
                timeout=30,
            )
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {e}"

    def run(self):
        print("AME Voice Agent activo")
        print("Di 'AME' para activar")
        self.running = True
        while self.running:
            text = self.listen()
            if text and "ame" in text:
                command = text.replace("ame", "").strip()
                if command:
                    response = self.process_command(command)
                    print(f"AME: {response}")
                    try:
                        import pyttsx3

                        engine = pyttsx3.init()
                        engine.say(response[:200])
                        engine.runAndWait()
                    except Exception:
                        pass


if __name__ == "__main__":
    agent = VoiceAgent()
    agent.run()
