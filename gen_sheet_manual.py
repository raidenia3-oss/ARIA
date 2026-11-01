import sys
sys.path.insert(0,"ARIA_APP")
import chibi_art, gen_imagen, time, os, cv2, numpy as np
from PIL import Image
from rembg import remove, new_session
destino = chibi_art._TEMA_DIR("cyberpunk")
tmp = os.path.join(destino, "_tmp")
os.makedirs(tmp, exist_ok=True)
session = new_session()
filas = []
for i,(estado,pose) in enumerate(chibi_art.POSES):
    prompt = chibi_art.PROMPT_BASE + ", " + pose
    jpg = os.path.join(tmp, estado+".jpg")
    r = gen_imagen.generar(prompt, w=256, h=256, archivo=jpg, seed=3000+i)
    if not r.get("ok"):
        print("ERR", estado, r)
        break
    with Image.open(jpg) as im:
        im2 = chibi_art._recortar_marca(im.convert("RGBA"))
        out = remove(im2, session=session)
        png = os.path.join(tmp, estado+".png")
        out.save(png)
    cell = cv2.imread(png, cv2.IMREAD_UNCHANGED)
    if cell is None:
        print("ERR read", estado)
        break
    if cell.shape[0]!=256 or cell.shape[1]!=256:
        cell = cv2.resize(cell,(256,256))
    filas.append((estado,cell))
    if i < len(chibi_art.POSES)-1:
        time.sleep(16)
if len(filas)==7:
    canvas = np.zeros((256*len(filas),256,4),dtype=np.uint8)
    states_cfg = {}
    for i,(estado,cell) in enumerate(filas):
        canvas[i*256:(i+1)*256,0:256]=cell
        states_cfg[estado]={"fila":i,"frames":1,"fps":6}
    sheet = os.path.join(destino,"sheet.png")
    cv2.imwrite(sheet,canvas)
    import json
    cfg = {"frame_w":256,"frame_h":256,"states":states_cfg,"eye_box":chibi_art.EYE_BOX,"mouth_box":chibi_art.MOUTH_BOX,"base_state":"idle","poses":[e for e,_ in chibi_art.POSES]}
    with open(os.path.join(destino,"config.json"),"w",encoding="utf-8") as f:
        json.dump(cfg,f,ensure_ascii=False,indent=2)
    print({"ok":True,"sheet":sheet})
else:
    print({"error":"incomplete","count":len(filas)})
