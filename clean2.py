path = r'C:\Users\User\Downloads\AURA\backend\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()
bad = '''    def chat(self, message: str = \"\", history: list | None = None, provider: str | None = None, **kwargs) -> dict:
        return self.think(prompt=message, history=history, **kwargs)

    def process(self, prompt: str = \"\", **kwargs) -> dict:
        return self.think(prompt=prompt, **kwargs)
'''
if bad in s:
    s = s.replace(bad, '')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)
    print('ok')
else:
    print('none')
