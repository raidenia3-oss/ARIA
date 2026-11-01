path = r'C:\Users\User\Downloads\AURA\backend\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()
bad_block = '''    def chat(self, message: str = \"\", history: list | None = None, provider: str | None = None, **kwargs) -> dict:
        return self.think(prompt=message, history=history, **kwargs)

    def process(self, prompt: str = \"\", **kwargs) -> dict:
        return self.think(prompt=prompt, **kwargs)

    def think(self, prompt: str = \"\", history: list | None = None, **kwargs) -> dict:
        text = (prompt or '').strip()
        if not text:
            return {'message': 'Empty prompt.', 'provider': 'local', 'source': 'unified_brain', 'confidence': 0.9}
        response = f'[AURA:UNIFIED] {text} (ok)'
        try:
            self.learn(device='pc', role='core', prompt=text, response=response, provider='unified_brain')
        except Exception:
            pass
        return {'message': response, 'provider': 'unified_brain', 'source': 'think', 'confidence': 0.95}
'''
if bad_block in s:
    s = s.replace(bad_block, '')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)
    print('ok')
else:
    print('none')
