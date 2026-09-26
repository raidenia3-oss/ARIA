"""Intent Detector — Mejor precisión de detección de intención"""

import asyncio
from typing import Dict


class IntentDetector:
    """Detector de intención con mejor precisión"""

    def __init__(self):
        self.extended_map = {
            'prendete': {'intent': 'activate', 'confidence': 0.99},
            'despierta': {'intent': 'activate', 'confidence': 0.95},
            'enciende': {'intent': 'activate', 'confidence': 0.93},
            'hola': {'intent': 'greet', 'confidence': 0.90},
            'buenos': {'intent': 'greet', 'confidence': 0.88},
            'usb': {'intent': 'usb', 'confidence': 0.99},
            'expande': {'intent': 'expand', 'confidence': 0.95},
            'maximiza': {'intent': 'maximize', 'confidence': 0.90},
            'aprende': {'intent': 'learn', 'confidence': 0.95},
            'memoriza': {'intent': 'learn', 'confidence': 0.90},
            'recuerda': {'intent': 'learn', 'confidence': 0.85},
            '¿qué': {'intent': 'query', 'confidence': 0.80},
            'dime': {'intent': 'query', 'confidence': 0.75},
            'hora': {'intent': 'query', 'confidence': 0.85},
            'tiempo': {'intent': 'query', 'confidence': 0.80},
            'clima': {'intent': 'query', 'confidence': 0.82},
            'busca': {'intent': 'search', 'confidence': 0.90},
            'buscar': {'intent': 'search', 'confidence': 0.92},
            'abre': {'intent': 'open', 'confidence': 0.88},
            'abrir': {'intent': 'open', 'confidence': 0.90},
            'cerrar': {'intent': 'close', 'confidence': 0.85},
            'detente': {'intent': 'stop', 'confidence': 0.90},
            'para': {'intent': 'stop', 'confidence': 0.80},
            'reproduce': {'intent': 'play', 'confidence': 0.88},
            'pausa': {'intent': 'pause', 'confidence': 0.85},
            'siguiente': {'intent': 'next', 'confidence': 0.82},
        }

    async def detect(self, user_input: str) -> Dict:
        """Detecta intención con scoring mejorado"""
        user_input_lower = user_input.lower()
        best_match = None
        highest_confidence = 0

        for keyword, intent_data in self.extended_map.items():
            keyword_clean = keyword.strip()
            if keyword_clean in user_input_lower:
                if intent_data['confidence'] > highest_confidence:
                    best_match = intent_data
                    highest_confidence = intent_data['confidence']

        if best_match:
            return best_match
        return {'intent': 'conversation', 'confidence': 0.70}


if __name__ == '__main__':
    import asyncio
    detector = IntentDetector()
    test_inputs = [
        "Prendete ARIA",
        "¿Qué hora es?",
        "USB conectado",
        "Busca información",
    ]
    for inp in test_inputs:
        result = asyncio.run(detector.detect(inp))
        print(f"Input: {inp} → Intent: {result}")
