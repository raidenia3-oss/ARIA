# -*- coding: utf-8 -*-
"""ARIA - Generador de demos interactivas (de Every Joule, pedagogia POE).

Cuando ARIA te ensena un concepto, no solo lo explica: genera una DEMO INTERACTIVA
(canvas) con estructura Predecir -> Observar/Probar -> Explicar (POE, metodo con
respaldo de investigacion, potenciado con simulaciones). Tu predices, la mueves,
y recien ahi se revela la explicacion. El aprendizaje se vuelve tangible.

Autocontenida: canvas + JS vanilla, SIN dependencias ni CDN (Regla v2). Estilo cyan
de ARIA. Se guarda a un .html y se abre en el navegador / QWebEngineView.

Tipos: 'oscilacion' (energia KE<->PE tipo Every Joule), 'grafica' (y=f(x) con slider),
'proyectil' (tiro con angulo/velocidad), 'formula' (sliders -> resultado en vivo).

La generacion del HTML (generar_demo) es PURA: testeable (produce un string valido).
"""
import os
import json

TIPOS = ("oscilacion", "grafica", "proyectil", "formula")

_CSS = """
:root{--bg:#070b14;--cyan:#38bdf8;--viol:#a78bfa;--teal:#2dd4bf;--txt:#cfe8ff;--verde:#7dffb0}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);
font-family:Consolas,'JetBrains Mono',monospace}
.wrap{max-width:720px;margin:0 auto;padding:18px}
h1{color:var(--cyan);font-size:20px;letter-spacing:2px;margin:6px 0 2px}
.sub{color:var(--teal);font-size:12px;margin-bottom:14px}
.paso{border:1px solid rgba(56,189,248,.35);border-radius:10px;padding:14px;margin:12px 0;
background:rgba(2,6,14,.5)}
.paso.off{opacity:.4;pointer-events:none}
.badge{display:inline-block;font-size:11px;color:var(--bg);background:var(--cyan);
border-radius:4px;padding:2px 8px;font-weight:700;letter-spacing:1px}
button{background:rgba(56,189,248,.18);color:var(--cyan);border:1px solid var(--cyan);
border-radius:6px;padding:8px 12px;font-family:inherit;font-weight:700;cursor:pointer;margin:4px}
button:hover{background:rgba(56,189,248,.4)}
button.sel{background:var(--cyan);color:var(--bg)}
canvas{width:100%;background:#040810;border:1px solid rgba(56,189,248,.3);border-radius:8px;margin-top:8px}
.ctrl{display:flex;align-items:center;gap:10px;margin-top:8px;font-size:12px}
input[type=range]{flex:1;accent-color:var(--cyan)}
.bars{display:flex;gap:10px;margin-top:8px}
.bar{flex:1;text-align:center;font-size:11px}
.bar .m{height:60px;background:rgba(56,189,248,.12);border-radius:5px;position:relative;overflow:hidden;margin-top:4px}
.bar .f{position:absolute;bottom:0;left:0;right:0;transition:height .1s}
.exp{color:var(--txt);line-height:1.5;font-size:13px}
.ver{font-weight:700;margin-bottom:6px}
"""

# motor JS: controla el flujo POE y dibuja segun cfg.tipo
_JS = r"""
const CFG = __CFG__;
const $ = s => document.querySelector(s);
function paso(n){[1,2,3].forEach(i=>$('#p'+i).classList.toggle('off', i>n));}
let eleccion=null;
document.querySelectorAll('.opt').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.opt').forEach(x=>x.classList.remove('sel'));
  b.classList.add('sel'); eleccion=b.dataset.v; $('#bprobar').disabled=false;});
$('#bprobar').onclick=()=>{paso(2); iniciar();};
$('#bexp').onclick=()=>{
  paso(3);
  const ok = (CFG.correcta==null) ? null : (eleccion===String(CFG.correcta));
  const v=$('#ver');
  if(ok===null){v.textContent='';}
  else{v.textContent= ok?'Prediccion correcta ✓':'No era esa — mira por que:';
       v.style.color= ok?'var(--verde)':'var(--viol)';}
};
// ---- canvas helpers ----
let cv,ctx,raf,t0;
function iniciar(){cv=$('#cv');ctx=cv.getContext('2d');
  cv.width=cv.clientWidth*2;cv.height=360; t0=performance.now();
  cancelAnimationFrame(raf); loop();}
function val(id){const e=$('#'+id); return e?parseFloat(e.value):0;}
function loop(){const t=(performance.now()-t0)/1000;
  ctx.clearRect(0,0,cv.width,cv.height);
  ({oscilacion:dOsc,grafica:dGraf,proyectil:dProy,formula:dForm}[CFG.tipo]||dForm)(t);
  raf=requestAnimationFrame(loop);}
function txt(s,x,y,c){ctx.fillStyle=c||'#cfe8ff';ctx.font='22px Consolas';ctx.fillText(s,x,y);}

// ---- oscilacion: energia KE<->PE (estilo Every Joule) ----
function dOsc(t){const W=cv.width,H=cv.height,k=val('s1'),A=120;
  const x=W/2+A*Math.cos(t*k); const pe=Math.pow(Math.cos(t*k),2), ke=1-pe;
  // resorte
  ctx.strokeStyle='#38bdf8';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(40,H/2);
  for(let i=0;i<=30;i++){const px=40+(x-40)*i/30;const py=H/2+(i%2?14:-14)*(i>0&&i<30);ctx.lineTo(px,py);}
  ctx.stroke();
  ctx.fillStyle='#a78bfa';ctx.beginPath();ctx.arc(x,H/2,24,0,7);ctx.fill();
  // barras de energia que 'fluyen'
  bar(W-220,'KE',ke,'#2dd4bf'); bar(W-110,'PE',pe,'#a78bfa');
  txt('energia: KE <-> PE',40,40,'#7dffb0');}
function bar(x,lab,v,c){const H=cv.height;ctx.fillStyle='rgba(255,255,255,.08)';
  ctx.fillRect(x,60,70,H-120);ctx.fillStyle=c;ctx.fillRect(x,60+(H-120)*(1-v),70,(H-120)*v);
  ctx.fillStyle='#cfe8ff';ctx.font='18px Consolas';ctx.fillText(lab,x+20,H-40);}

// ---- grafica y=f(x) con parametro ----
function dGraf(t){const W=cv.width,H=cv.height,a=val('s1');
  ctx.strokeStyle='rgba(56,189,248,.25)';ctx.beginPath();ctx.moveTo(0,H/2);ctx.lineTo(W,H/2);
  ctx.moveTo(W/2,0);ctx.lineTo(W/2,H);ctx.stroke();
  ctx.strokeStyle='#38bdf8';ctx.lineWidth=3;ctx.beginPath();
  for(let px=0;px<W;px++){const x=(px-W/2)/60;let y;
    try{y=eval(CFG.formula||'a*x*x');}catch(e){y=0;}
    const py=H/2-y*30; px?ctx.lineTo(px,py):ctx.moveTo(px,py);}
  ctx.stroke(); txt((CFG.etiqueta||'y=a*x^2')+'  a='+a.toFixed(2),40,40,'#7dffb0');}

// ---- proyectil ----
function dProy(t){const W=cv.width,H=cv.height,ang=val('s1')*Math.PI/180,v=val('s2');
  const g=160,vx=v*Math.cos(ang),vy=v*Math.sin(ang);
  ctx.strokeStyle='#2dd4bf';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(40,H-30);
  for(let tt=0;tt<4;tt+=0.03){const x=40+vx*tt*40,y=H-30-(vy*tt-0.5*g*tt*tt)*40;
    if(y>H)break; ctx.lineTo(x,y);} ctx.stroke();
  const tt=(t%3),x=40+vx*tt*40,y=H-30-(vy*tt-0.5*g*tt*tt)*40;
  if(y<=H){ctx.fillStyle='#a78bfa';ctx.beginPath();ctx.arc(x,y,12,0,7);ctx.fill();}
  txt('angulo '+val('s1').toFixed(0)+'°  v='+v.toFixed(1),40,40,'#7dffb0');}

// ---- formula: sliders -> resultado ----
function dForm(t){const W=cv.width,H=cv.height,a=val('s1'),b=val('s2');let r;
  try{r=eval(CFG.formula||'a*b');}catch(e){r=0;}
  ctx.fillStyle='#38bdf8';ctx.font='bold 54px Consolas';
  ctx.fillText((CFG.etiqueta||'a*b')+' = '+(r).toFixed(2),40,H/2);
  const mx=Math.max(1,CFG.max||100),w=(W-80)*Math.min(1,Math.abs(r)/mx);
  ctx.fillStyle='rgba(56,189,248,.5)';ctx.fillRect(40,H/2+30,w,30);}
"""


def _controles(tipo, config):
    """Sliders segun el tipo (HTML)."""
    def s(id, lab, mn, mx, val, step=0.1):
        return ('<div class="ctrl"><span>%s</span>'
                '<input type="range" id="%s" min="%s" max="%s" value="%s" step="%s"></div>'
                % (lab, id, mn, mx, val, step))
    if tipo == "oscilacion":
        return s("s1", config.get("lab1", "rigidez (k)"), 0.5, 4, config.get("v1", 2))
    if tipo == "grafica":
        return s("s1", config.get("lab1", "parametro a"), -3, 3, config.get("v1", 1))
    if tipo == "proyectil":
        return (s("s1", "angulo", 10, 80, config.get("v1", 45), 1)
                + s("s2", "velocidad", 1, 8, config.get("v2", 5)))
    return (s("s1", config.get("lab1", "a"), 0, config.get("max", 100), config.get("v1", 10), 1)
            + s("s2", config.get("lab2", "b"), 0, config.get("max", 100), config.get("v2", 10), 1))


def generar_demo(tipo="oscilacion", titulo="Demo", prediccion="",
                 opciones=None, correcta=None, explicacion="", config=None):
    """Genera una demo interactiva POE autocontenida. Devuelve el HTML (str)."""
    if tipo not in TIPOS:
        tipo = "formula"
    config = dict(config or {})
    opciones = opciones or ["sube", "baja", "no cambia"]
    cfg_js = {"tipo": tipo, "formula": config.get("formula"),
              "etiqueta": config.get("etiqueta"), "correcta": correcta,
              "max": config.get("max", 100)}
    botones = "".join('<button class="opt" data-v="%d">%s</button>' % (i, o)
                      for i, o in enumerate(opciones))
    html = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(titulo)s</title><style>%(css)s</style></head><body><div class="wrap">
<h1>%(titulo)s</h1><div class="sub">demo interactiva · predice, prueba, comprueba</div>

<div class="paso" id="p1"><span class="badge">1 · PREDICE</span>
<p>%(pred)s</p>%(botones)s
<div><button id="bprobar" disabled>Probar &rsaquo;</button></div></div>

<div class="paso off" id="p2"><span class="badge">2 · PRUEBA</span>
<canvas id="cv" height="360"></canvas>%(ctrl)s
<div><button id="bexp">Comprobar &rsaquo;</button></div></div>

<div class="paso off" id="p3"><span class="badge">3 · COMPRUEBA</span>
<div class="ver" id="ver"></div><div class="exp">%(exp)s</div></div>

</div><script>%(js)s</script></body></html>""" % {
        "titulo": titulo, "css": _CSS, "pred": prediccion or "Que crees que pasara?",
        "botones": botones, "ctrl": _controles(tipo, config),
        "exp": explicacion or "Observa como se relacionan las variables.",
        "js": _JS.replace("__CFG__", json.dumps(cfg_js)),
    }
    return html


def guardar_demo(html, ruta=None):
    """Guarda la demo a un .html (por defecto en data/demos/)."""
    if not ruta:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "demos")
        os.makedirs(d, exist_ok=True)
        ruta = os.path.join(d, "demo.html")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(html)
        return {"ok": True, "ruta": ruta}
    except Exception as exc:
        return {"error": str(exc)}


def para_concepto(concepto, tipo="oscilacion", **kw):
    """Atajo: arma una demo para un concepto con defaults sensatos."""
    return generar_demo(tipo=tipo, titulo=concepto,
                        prediccion=kw.get("prediccion", "Que pasara al mover el control?"),
                        opciones=kw.get("opciones"), correcta=kw.get("correcta"),
                        explicacion=kw.get("explicacion", ""), config=kw.get("config"))
