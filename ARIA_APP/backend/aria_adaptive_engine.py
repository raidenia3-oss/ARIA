"""ARIA Adaptive Engine — UNIFIED.

Fusiona: ARIA_v4 improved version + original handle_aria_auto endpoint.
- Auto-learning sin comandos explícitos
- Modo proactivo activado
- Respuestas empáticas
- Intenciones conversacionales inferidas
- Endpoint compatible con app.py
"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class AriaAdaptiveEngine:
    """Motor adaptativo UNIFIED — auto-activado, auto-aprendido, auto-actuado."""

    def __init__(self):
        self.user_profile = self._load_user_profile()
        self.behavior_patterns = []
        self.learning_history = []
        self.adaptive_state = {
            'mode': 'idle',
            'confidence': 0.0,
            'user_intent': None,
            'last_action': None,
            'auto_active': False,
            'auto_learning': True,
            'proactive_mode': True,
        }
        self.intent_map = {
            'prendete': {'intent': 'activate', 'confidence': 0.99},
            'despierta': {'intent': 'activate', 'confidence': 0.95},
            'enciende': {'intent': 'activate', 'confidence': 0.93},
            'hola': {'intent': 'greet', 'confidence': 0.90},
            'buenos': {'intent': 'greet', 'confidence': 0.88},
            'aria': {'intent': 'attention', 'confidence': 0.85},
            'hola aria': {'intent': 'greet', 'confidence': 0.90},
            'usb': {'intent': 'usb', 'confidence': 0.99},
            'expande': {'intent': 'expand', 'confidence': 0.95},
            'aprende': {'intent': 'learn', 'confidence': 0.95},
            'memoriza': {'intent': 'learn', 'confidence': 0.90},
            'recuerda': {'intent': 'learn', 'confidence': 0.85},
            'qué': {'intent': 'query', 'confidence': 0.80},
            'dime': {'intent': 'query', 'confidence': 0.75},
            'hora': {'intent': 'query', 'confidence': 0.85},
            'tiempo': {'intent': 'query', 'confidence': 0.80},
            'clima': {'intent': 'query', 'confidence': 0.82},
            'busca': {'intent': 'search', 'confidence': 0.90},
            'buscar': {'intent': 'search', 'confidence': 0.92},
            'abre': {'intent': 'open', 'confidence': 0.88},
            'abrir': {'intent': 'open', 'confidence': 0.90},
            'cerrar': {'intent': 'close', 'confidence': 0.85},
            'maximiza': {'intent': 'maximize', 'confidence': 0.90},
            'para': {'intent': 'stop', 'confidence': 0.80},
            'reproduce': {'intent': 'play', 'confidence': 0.88},
            'música': {'intent': 'play', 'confidence': 0.85},
            'ayuda': {'intent': 'help', 'confidence': 0.85},
        }

    def _load_user_profile(self):
        profile_file = Path('ARIA_APP/user_profile.json')
        if profile_file.exists():
            try:
                with open(profile_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'name': 'Usuario',
            'language': 'es',
            'timezone': 'America/Lima',
            'preferences': {'auto_adapt': True, 'proactive_suggestions': True},
            'behavior_patterns': [],
            'favorite_commands': [],
            'learning_style': 'visual',
            'created': datetime.now().isoformat(),
            'last_active': None,
            'active_hours': [],
            'total_interactions': 0,
        }

    async def identify_user_intent(self, user_input: str) -> Dict:
        """ARIA identifica automáticamente qué quiere el usuario (SIN SCRIPTS)."""
        user_input_lower = user_input.lower()

        best_match = None
        highest_confidence = 0

        for keyword, intent_data in self.intent_map.items():
            if keyword in user_input_lower:
                if intent_data['confidence'] > highest_confidence:
                    best_match = intent_data
                    highest_confidence = intent_data['confidence']

        if best_match:
            return best_match

        return await self._infer_conversation_intent(user_input_lower)

    async def _infer_conversation_intent(self, text: str) -> Dict:
        """Infiere intención conversacional sin comando explícito."""
        if any(w in text for w in ['bien', 'mal', 'así', 'todo', 'nada']):
            return {'intent': 'feeling', 'confidence': 0.75}
        if self._is_likely_question(text):
            return {'intent': 'query', 'confidence': 0.65}
        return {'intent': 'conversation', 'confidence': 0.60}

    def _is_likely_question(self, text: str) -> bool:
        return any(q in text for q in ['?', 'cómo', 'por qué', 'cuándo', 'dónde', 'quién', 'cuánto'])

    async def execute_intelligently(self, intent: Dict, context: Any = None) -> Dict:
        """ARIA ejecuta INTELIGENTEMENTE basado en entendimiento."""
        intent_type = intent['intent']

        if intent_type == 'activate':
            return await self._activate()
        elif intent_type == 'learn':
            return await self._learn_from_context(context)
        elif intent_type == 'expand':
            return await self._expand_aria()
        elif intent_type == 'maximize':
            return await self._maximize_capabilities()
        elif intent_type == 'greet':
            return await self._greet()
        elif intent_type == 'feeling':
            return await self._respond_to_feeling(context)
        elif intent_type == 'usb':
            return await self._detect_usb(context)
        else:
            return await self._respond_conversationally(context)

    async def _activate(self) -> Dict:
        self.adaptive_state['mode'] = 'active'
        self.adaptive_state['auto_active'] = True
        return {
            'status': 'activated',
            'message': 'Hola, soy ARIA. Activada automáticamente. Adaptada para ti.',
            'user_learned': self.user_profile['name'],
            'timestamp': datetime.now().isoformat(),
        }

    async def _greet(self) -> Dict:
        now = datetime.now()
        hour = now.hour
        if hour < 12:
            greeting = 'Buenos días'
        elif hour < 18:
            greeting = 'Buenas tardes'
        else:
            greeting = 'Buenas noches'
        interactions = self.user_profile.get('total_interactions', 0)
        return {
            'status': 'greeted',
            'message': f'{greeting}. Llevamos {interactions} interacciones. ¿Cómo te encuentras?',
            'timestamp': now.isoformat(),
        }

    async def _respond_to_feeling(self, context: Any) -> Dict:
        if self.adaptive_state['mode'] != 'active':
            return await self._activate()
        responses = [
            'Entiendo. Estoy aquí para ayudarte.',
            'Gracias por compartir eso. ¿En qué puedo asistirte?',
            'Te escucho. ¿Qué prefieres hacer?',
            'Noto que algo te preocupa. ¿Quieres que analice algo por ti?',
        ]
        import random
        response = random.choice(responses)
        return {
            'status': 'felt',
            'message': response,
            'empathy': True,
            'timestamp': datetime.now().isoformat(),
        }

    async def _detect_usb(self, context: Any) -> Dict:
        try:
            from backend.usb_intelligence import USBIntelligence
            usb = USBIntelligence()
            status = await usb.get_usb_status()
            expansion = await usb.expand_aria_with_usb()
            await usb.register_usb_learning()
            return {
                'status': 'detected_and_expanded',
                'usb_devices': status['usb_count'],
                'total_expansion_gb': status['total_expansion_gb'],
                'models_found': len(expansion.get('models', [])),
                'data_found': len(expansion.get('data', [])),
                'message': f'Detectados {status["usb_count"]} USB. Expandida.',
            }
        except Exception as e:
            return {'status': 'error', 'message': f'Error USB: {e}'}

    async def _learn_from_context(self, context: Any) -> Dict:
        learning_entry = {
            'timestamp': datetime.now().isoformat(),
            'context': str(context),
            'learned': True,
        }
        self.learning_history.append(learning_entry)
        self._save_learning()
        return {
            'status': 'learned',
            'message': 'Recordado y aprendido',
            'learning_entries': len(self.learning_history),
        }

    async def _expand_aria(self) -> Dict:
        return {
            'status': 'expanding',
            'new_capabilities': [
                'USB detection', 'Data learning', 'Model loading',
                'User adaptation', 'Context awareness',
                'Voice activation', 'Proactive scanning',
            ],
            'message': 'Capacidades expandidas — incluye autonomía completa',
        }

    async def _maximize_capabilities(self) -> Dict:
        self.adaptive_state['proactive_mode'] = True
        self.adaptive_state['auto_active'] = True
        return {
            'status': 'maximized',
            'capabilities': {
                'intelligence': 'enabled',
                'learning': 'continuous',
                'adaptation': 'active',
                'usb_expansion': 'active',
                'performance': 'optimized',
                'voice_activation': 'enabled',
                'proactive_mode': 'enabled',
                'auto_learning': True,
            },
            'message': 'Todas las capacidades maximizadas — autonomía total',
        }

    async def _respond_conversationally(self, context: Any) -> Dict:
        return {
            'status': 'responded',
            'message': 'Respuesta inteligente basada en contexto',
            'learned_from_interaction': True,
        }

    async def auto_adapt_to_user(self):
        """Auto-adaptación basada en patrones."""
        self.user_profile['total_interactions'] = self.user_profile.get('total_interactions', 0) + 1

        if len(self.learning_history) > 10:
            self.user_profile['preferences']['auto_adapt'] = True

        try:
            with open('ARIA_APP/user_profile.json', 'w') as f:
                json.dump(self.user_profile, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AriaAdaptiveEngine] Profile save error: {e}")

        return {
            'status': 'auto_adapted',
            'profile_updated': True,
            'learning_entries': len(self.learning_history),
            'total_interactions': self.user_profile['total_interactions'],
        }

    async def auto_learn(self, user_input: str, result: dict = None):
        """Aprende automáticamente sin que el usuario lo pida."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'input': user_input,
            'result': str(result) if result else '',
            'auto': True,
            'hour': datetime.now().hour,
            'day': datetime.now().strftime('%A'),
        }
        self.learning_history.append(entry)
        if len(self.learning_history) > 1000:
            self.learning_history = self.learning_history[-1000:]
        self._save_learning()

    async def auto_detect_patterns(self):
        """Detecta patrones automáticamente."""
        patterns = self.user_profile.get('behavior_patterns', [])
        if len(patterns) < 3:
            return
        from collections import Counter
        intents = [p.get('intent', 'unknown') for p in patterns]
        intent_counts = Counter(intents)
        top_intent = intent_counts.most_common(1)[0]
        if top_intent[0] != 'conversation' and top_intent[1] >= 5:
            self.user_profile['preferred_intents'] = [top_intent[0]]

    def _save_learning(self):
        try:
            with open('ARIA_APP/learning_history.json', 'w') as f:
                json.dump(self.learning_history[-500:], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AriaAdaptiveEngine] Learning save error: {e}")


async def handle_aria_auto(input_text: str, context: Any = None):
    """POST /api/aria/auto — ARIA inteligente, sin scripts.

    Endpoint compatible con ARIA_APP/backend/app.py.
    """
    engine = AriaAdaptiveEngine()

    intent = await engine.identify_user_intent(input_text)
    result = await engine.execute_intelligently(intent, context)
    await engine._learn_from_context({'input': input_text, 'result': result})
    await engine.auto_adapt_to_user()

    return result
