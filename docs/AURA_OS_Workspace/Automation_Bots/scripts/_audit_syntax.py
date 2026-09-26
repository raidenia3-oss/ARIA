import ast
import sys

files = [
    'AME_Core/servidor_ame.py',
    'AURA_Core/ai_router.py',
    'AURA_Core/osint_radar.py',
    'AURA_Core/void.py',
    'AURA_Core/skills_forge.py',
    'AME_Core/ame_client.py',
]

errors = 0
for f in files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        print(f'  ✅ {f.split(chr(92))[-1][:30]} SINTAXIS OK')
    except SyntaxError as e:
        print(f'  ❌ {f.split(chr(92))[-1][:30]} ERROR: {e}')
        errors += 1
    except FileNotFoundError:
        print(f'  ⚠️  {f} NO ENCONTRADO')

print(f'\nTotal errores de sintaxis: {errors}')
sys.exit(errors)