import os,json,cv2,numpy as np
size=256
dest='ARIA_APP/assets/chibi/cyberpunk'
tmp=os.path.join(dest,'_tmp')
poses=[('idle',''),('walk',''),('talk',''),('think',''),('listen',''),('sleep',''),('react','')]
filas=[]
for estado,_ in poses:
    png=os.path.join(tmp,f'{estado}.png')
    if not os.path.exists(png):
        raise SystemExit(f'FALTA {png}')
    cell=cv2.imread(png,cv2.IMREAD_UNCHANGED)
    if cell is None: raise SystemExit(2)
    if cell.shape[0]!=size or cell.shape[1]!=size: cell=cv2.resize(cell,(size,size))
    filas.append((estado,cell))
canvas=np.zeros((size*len(filas),size,4),dtype=np.uint8)
scfg={}
for i,(e,c) in enumerate(filas):
    canvas[i*size:(i+1)*size,0:size]=c
    scfg[e]={'fila':i,'frames':1,'fps':6}
sheet=os.path.join(dest,'sheet.png')
cv2.imwrite(sheet,canvas)
cfg={'frame_w':size,'frame_h':size,'states':scfg,'eye_box':[0.18,0.30,0.82,0.44],'mouth_box':[0.34,0.50,0.66,0.60],'base_state':'idle'}
with open(os.path.join(dest,'config.json'),'w',encoding='utf-8') as f: json.dump(cfg,f,indent=2)
print({'ok':True,'sheet':sheet,'poses':len(filas)})
