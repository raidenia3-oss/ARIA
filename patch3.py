path = r'C:\Users\User\Downloads\AURA\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()
# actual block
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
if old not in s:
    print('no')
else:
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
                prompt = self._build_prompt(message, context) if hasattr(self, "_build_prompt") else message
                resp = self.brain.generate(prompt)
                if resp and len(str(resp).strip()) > 2:
                    return {"message": str(resp), "provider": "local", "latency": 0.1, "source": "local_model"}
        except Exception:
            pass
        return None'''
    s = s.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)
    print('ok')
