p = r'C:\Users\User\Downloads\AURA\v5\src\App.tsx'
s = open(p, encoding='utf-8').read()
old = '<div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-bg-dark-0 via-bg-dark-1 to-bg-dark-2 opacity-80" />'
new = '<div className="aurora pointer-events-none absolute inset-0" /><div className="mesh-ambient pointer-events-none absolute inset-0" />'
if old in s:
    s2 = s.replace(old,new)
    open(p,'w',encoding='utf-8').write(s2)
    print('ok')
else:
    print('not found')
