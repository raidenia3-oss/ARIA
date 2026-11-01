path = r'C:\Users\User\Downloads\AURA\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()

old = '''    def _try_local_model(self, message: str, context: str) -> Optional[Dict[str, Any]]:
        if not self.brain or not self.brain.model_loaded:
            return None
        prompt = self._build_prompt(message, context)
        response = self.brain.generate(prompt)
        if response and len(response.strip()) > 3:
            return {
                "message": response,
                "provider": "local",
                "latency": 0.1,
                "source": "local_model",
            }
        return None'''

new = '''    def _try_local_model(self, message: str, context: str) -> Optional[Dict[str, Any]]:
        if not self.brain:
            return None
        if hasattr(self.brain, "think"):
            try:
                resp = self.brain.think(message, context)
                if resp and resp.get("message"):
                    return resp
            except Exception:
                pass
        if not getattr(self.brain, "model_loaded", False):
            return None
        try:
            if hasattr(self.brain, "generate"):
                prompt = getattr(self, "_build_prompt", lambda m,c: m)(message, context)
                response = self.brain.generate(prompt)
                if response and len(str(response).strip()) > 2:
                    return {"message": str(response), "provider": "local", "latency": 0.1, "source": "local_model"}
        except Exception:
            pass
        return None'''

if old not in s:
    raise SystemExit('no')
s = s.replace(old, new)
with open(path, 'w', encoding='utf-8') as f:
    f.write(s)
print('ok')
