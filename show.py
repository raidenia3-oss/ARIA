p = r'C:\Users\User\Downloads\AURA\v5\src\components\OrbVisual\OrbVisual.tsx'
with open(p,encoding='utf-8') as f:
    lines = f.readlines()
for i,l in enumerate(lines[440:480],441):
    print(f'{i}: {l}', end='')
