"""STT Engine — Vosk + Whisper"""

class STTEngine:
    """Speech-to-Text"""

    def __init__(self):
        self.provider = 'vosk'
        self.supported_languages = ['es', 'en']

    def transcribe(self, audio_path: str) -> dict:
        return {
            'status': 'ok',
            'text': '[transcripción simulada]',
            'language': 'es',
            'engine': self.provider,
        }

    def is_available(self) -> bool:
        return True


class TTSEngine:
    """Text-to-Speech"""

    def __init__(self):
        self.provider = 'edge-tts'
        self.default_voice = 'es-ES-ElviraNeural'

    def speak(self, text: str, voice: str = None) -> dict:
        return {
            'status': 'ok',
            'audio': f'[TTS: {text[:50]}...]',
            'voice': voice or self.default_voice,
        }

    def is_available(self) -> bool:
        return True


class AudioManager:
    """Gestión de audio I/O"""

    def __init__(self):
        self.stt = STTEngine()
        self.tts = TTSEngine()
