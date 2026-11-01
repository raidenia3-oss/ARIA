path = r'C:\Users\User\Downloads\AURA\aura_app.py'
with open(path, 'r', encoding='utf-8') as f:
    s = f.read()

# try to import unified brain
header = '''try:
    from backend.brain_orchestrator import brain as UNIFIED_BRAIN
except Exception:
    UNIFIED_BRAIN = None
'''

if 'UNIFIED_BRAIN' not in s:
    # insert after AuraBrainAPI import block? simple: after BrainOrchestrator import area
    s2 = s.replace('BrainOrchestrator = None\n\n', 'BrainOrchestrator = None\n\n' + header + '\n')
    s = s2

# use unified brain if present
old = '''        self.brain = AuraBrain() if AuraBrain else None
        self.brain_api = AuraBrainAPI() if AuraBrainAPI else None
        if self.brain:
            self.brain.load_model()
        self.orchestrator = BrainOrchestrator(
            brain=self.brain,
            brain_api=self.brain_api,
            ai_manager=self.ai,
        ) if BrainOrchestrator else None'''
new = '''        self.brain = UNIFIED_BRAIN if UNIFIED_BRAIN is not None else (AuraBrain() if AuraBrain else None)
        self.brain_api = AuraBrainAPI() if AuraBrainAPI else None
        try:
            if hasattr(self.brain, 'load_model'):
                self.brain.load_model()
        except Exception:
            pass
        try:
            if hasattr(self.brain, 'model_loaded'):
                pass
        except Exception:
            pass
        self.orchestrator = BrainOrchestrator(
            brain=self.brain,
            brain_api=self.brain_api,
            ai_manager=self.ai,
        ) if BrainOrchestrator else None'''
if old not in s:
    print('no')
else:
    s = s.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)
    print('ok')
