path = r'C:\Users\User\Downloads\AURA\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()

# replace _try_local_model
old = '''    def _try_local_model(self, message: str, context: str) -> Optional[Dict[str, Any]]:
        if not self.brain or not self.brain.model_loaded:
            return None
        try:
            start = time.time()
            resp = self.brain.chat(message, context)
            latency = time.time() - start
            text = resp.get("message", "")
            if text and len(text.strip()) > 2:
                return {
                    "message": text,
                    "provider": "local",
                    "latency": round(latency, 2),
                    "source": "local_model",
                }
        except Exception:
            pass
        return None'''

new = '''    def _try_local_model(self, message: str, context: str) -> Optional[Dict[str, Any]]:
        if not self.brain:
            return None
        # Use unified brain if available
        if hasattr(self.brain, "think"):
            try:
                resp = self.brain.think(message, context)
                if resp and resp.get("message"):
                    return {**resp, "source": resp.get("source", "local_model"), "provider": resp.get("provider", "local")}
            except Exception:
                pass
        if not getattr(self.brain, "model_loaded", False):
            return None
        try:
            start = time.time()
            if hasattr(self.brain, "chat"):
                resp = self.brain.chat(message, context)
            else:
                resp = {"message": str(self.brain.generate(message))} if hasattr(self.brain, "generate") else {}
            latency = time.time() - start
            text = resp.get("message", "")
            if text and len(text.strip()) > 2:
                return {
                    "message": text,
                    "provider": "local",
                    "latency": round(latency, 2),
                    "source": "local_model",
                }
        except Exception:
            pass
        return None'''

if old not in s:
    raise SystemExit('no')
s = s.replace(old, new)
with open(path, 'w', encoding='utf-8') as f:
    f.write(s)
print('ok')
