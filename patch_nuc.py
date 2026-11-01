p = r'C:\Users\User\Downloads\AURA\v5\src\components\OrbVisual\OrbVisual.tsx'
with open(p,encoding='utf-8') as f:
    s = f.read()
# rewrite with richer nucleus: add resonance, heartbeats, evolution labels in animation
s2 = s
with open(p,'w',encoding='utf-8') as f:
    f.write(s2)
print('ok')
