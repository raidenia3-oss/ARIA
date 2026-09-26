import sys, time
sys.path.insert(0,r'AURA_APP')
sys.path.insert(0,r'.')
sys.path.insert(0,r'AURA_APP/backend')
import ai_providers as A
m=A.AIProviderManager()
g=m.chat_stream_ollama('Saluda en una frase')
print('generator OK:', hasattr(g,'__next__'))
for i,p in enumerate(g):
    print('chunk', i, repr(p))
    if i>=2: break
print('done after break')
