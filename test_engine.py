"""Test LogicEngine directly."""
import sys, os
sys.path.insert(0, 'AURA_APP')
os.environ['AURA_LOGIC_PROCESS'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'
import aria_logic_engine
e = aria_logic_engine.LogicEngine()
print('Engine created')
r = e.handle_chat('Hola')
print(f'Chat result: {r.get("status")} - {r.get("response","")[:80]}')
print('Done')