# -*- coding: utf-8 -*-
"""AURA OS - Chunk 3: Local Inference.

Wrapper para Jan con manejo de timeouts y fallback.
"""
from __future__ import annotations

import json, logging, os, time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger('AURA.LocalInference')

JAN_BASE_URL = os.environ.get('JAN_URL', 'http://localhost:1337/v1')
JAN_TIMEOUT = float(os.environ.get('JAN_TIMEOUT', '10'))
JAN_MODEL = os.environ.get('JAN_MODEL', 'llama3.1-8b')


class LocalInference:
    def __init__(self, base_url=None, timeout=None, model=None):
        self._base_url = base_url or JAN_BASE_URL
        self._timeout = timeout or JAN_TIMEOUT
        self._model = model or JAN_MODEL
        self._cache = {}
        self._cache_ttl = 300
        self._requests = 0
        self._errors = 0
        self._last_error = None
        self._last_success = None

    async def chat_completion(self, messages, temperature=0.7, max_tokens=1024, stream=False, model=None):
        self._requests += 1
        key = json.dumps([{'role': m.get('role','user'), 'content': m.get('content','')} for m in messages], sort_keys=True)
        if key in self._cache and time.time() - self._cache[key].get('cached_at', 0) < self._cache_ttl:
            r = self._cache[key]['response'].copy()
            r['cached'] = True
            return r
        m = model or self._model
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(f'{self._base_url}/chat/completions', json={'model': m, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens})
                if r.status_code == 200:
                    data = r.json()
                    result = {'success': True, 'model': m, 'usage': data.get('usage', {}), 'choices': data.get('choices', []), 'timestamp': time.time(), 'source': 'jan', 'cached': False}
                    self._cache[key] = {'response': result, 'cached_at': time.time()}
                    self._last_success = f'OK ({r.elapsed.total_seconds()*1000:.0f}ms)'
                    self._errors = max(0, self._errors - 1)
                    return result
                else:
                    err = f'HTTP {r.status_code}: {r.text[:200]}'
                    logger.warning(err); self._errors += 1; self._last_error = err
                    return self._fallback(messages, temperature, max_tokens, err)
        except Exception as e:
            err = f'Error: {type(e).__name__}: {e}'
            logger.error(err); self._errors += 1; self._last_error = err
            return self._fallback(messages, temperature, max_tokens, err)

    def _fallback(self, messages, temp, max_tokens, err):
        last = messages[-1]['content'] if messages else ''
        intent = self._intent(last)
        return {'success': False, 'model': self._model, 'fallback': True, 'error': err,
                'response': self._text(intent, last, messages), 'timestamp': time.time(),
                'source': 'fallback', 'intent_detected': intent}

    def _intent(self, t):
        t = t.lower().strip()
        if any(w in t for w in ['hola','buenas','hey','saludos']): return 'greeting'
        if any(w in t for w in ['adios','chau','bye','nos vemos']): return 'farewell'
        if any(w in t for w in ['estado','status','salud','health','activo']): return 'status_check'
        if any(w in t for w in ['codigo','programar','escribir','funcion','clase','script']): return 'code_generation'
        if '?' in t or any(w in t for w in ['que es','quien','cual','como','por que','cuando','donde']): return 'question'
        if any(w in t for w in ['error','fallo','problema','bug','excepcion']): return 'error_report'
        return 'general'

    def _text(self, intent, msg, msgs):
        import random
        r = random.Random(hash(msg))
        texts = {
            'greeting': ['Hola, soy AURA. Como puedo ayudarte?', 'Buenas, en que te puedo servir?'],
            'farewell': ['Hasta luego, que tengas buen dia.', 'Chau, vuelve cuando necesites.'],
            'status_check': ['AURA opera normal. Servicio de IA no disponible ahora.', 'Sistema funcional. IA specialized no disponible.'],
            'code_generation': ['No puedo generar codigo ahora. Intenta mas tarde.', 'Para codigo avanzado, espera el servidor IA.'],
            'question': ['Tengo info basica. Para consultas avanzadas, espera el servidor IA.', 'Pregunta general: puedo ayudarte con lo que conozco.'],
            'error_report': ['Problema detectado. Revisa conexion e intenta de nuevo.', 'Error. Reinicia el servicio si persiste.'],
            'general': [f'AURA: entendi "{msg[:60]}..." (IA no disponible ahora).'],
        }
        return r.choice(texts.get(intent, texts['general']))

    def get_stats(self):
        t = self._requests; e = self._errors
        return {'base_url': self._base_url, 'timeout': self._timeout, 'model': self._model,
                'total_requests': t, 'successful': t - e, 'errors': e,
                'success_rate_pct': round(((t - e) / max(t, 1)) * 100, 2),
                'last_error': self._last_error, 'last_success': self._last_success,
                'cache_size': len(self._cache), 'jan_available': e == 0}

    def clear_cache(self): self._cache.clear()


_inference = None

def get_inference():
    global _inference
    if _inference is None: _inference = LocalInference()
    return _inference

def reset_inference(): global _inference; _inference = None


if __name__ == '__main__':
    import asyncio
    async def test():
        inf = get_inference()
        r = await inf.chat_completion([{'role':'user','content':'Hola'}])
        print(r)
        print(inf.get_stats())
        print('local_inference.py: OK')
    asyncio.run(test())
