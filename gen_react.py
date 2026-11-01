import sys,os,time
sys.path.insert(0,'ARIA_APP')
import gen_imagen, chibi_art
size=256; tema='cyberpunk'
tmp=os.path.join(chibi_art._TEMA_DIR(tema),'_tmp')
os.makedirs(tmp,exist_ok=True)
estado='react'
pose='surprised and flustered, wide cyan eyes, big blush, hands up'
prompt=chibi_art.PROMPT_BASE+', '+pose
jpg=os.path.join(tmp,f'{estado}.jpg')
r=None
for i in range(12):
    r=gen_imagen.generar(prompt,w=size,h=size,archivo=jpg,seed=1007+i*29,timeout=180)
    if r.get('ok'): break
    print('ERR',r,i); time.sleep(90+i*15)
print('GEN',r)
if not r.get('ok'): raise SystemExit(1)
png=os.path.join(tmp,f'{estado}.png')
qf=chibi_art.quitar_fondo(jpg,png)
print('QF',qf)
