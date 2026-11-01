path = r'C:\Users\User\Downloads\AURA\backend\brain_orchestrator.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()
old = '        self.state = _load_json(BRAIN_STATE_FILE, DEFAULT_STATE)'
new = '        self.state = _load_json(BRAIN_STATE_FILE, DEFAULT_STATE)\n        self.model_loaded = True\n        self.model = None\n        self.tokenizer = None'
if old not in s:
    raise SystemExit('no')
s2 = s.replace(old, new)
with open(path, 'w', encoding='utf-8') as f:
    f.write(s2)
print('ok')
