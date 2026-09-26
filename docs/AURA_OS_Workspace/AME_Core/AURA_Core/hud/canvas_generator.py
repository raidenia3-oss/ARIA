# AURA_Core/hud/canvas_generator.py
# Fase 24 - Canvas de Diagnóstico y Renderizado Algorítmico
# Genera coordenadas vectoriales X/Y del sistema para HUD visual

import json
import math
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("CanvasGenerator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

# Constantes geométricas
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 800
CENTER_X = CANVAS_WIDTH // 2
CENTER_Y = CANVAS_HEIGHT // 2
RADIUS_MAX = 320
RADIUS_MIN = 80
NODE_RADIUS = 28

RUTAS = {
    "grafo": "AURA_Core/knowledge_graph.json",
    "reporte": "AURA_Core/latest_report.json",
    "canvas": "AURA_Core/system_canvas.json",
    "telemetria": "telemetry_history.json",
}

COLORES = {
    "device": "#00ff88",
    "backend": "#00aaff",
    "service": "#ffaa00",
    "module": "#ff66cc",
    "ui": "#aa66ff",
    "default": "#888888",
}

_ws_callback: Optional[Any] = None


def attach_ws(callback: Any) -> None:
    global _ws_callback
    _ws_callback = callback


def _dispatch(event: str, payload: Any) -> None:
    if _ws_callback:
        try:
            _ws_callback(json.dumps({"event": event, "payload": payload}))
        except Exception as e:
            logger.error(f"Error en dispatch WS: {e}")


def _load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _layout_circular(n: int) -> List[Tuple[float, float]]:
    pos = []
    for i in range(n):
        a = (2 * math.pi * i / max(n, 1)) - math.pi / 2
        r = RADIUS_MAX if n > 4 else RADIUS_MIN
        pos.append((round(CENTER_X + r * math.cos(a), 1), round(CENTER_Y + r * math.sin(a), 1)))
    return pos


def _color(t: str) -> str:
    return COLORES.get(t, COLORES["default"])


def _emoji(s: str) -> str:
    if str(s) in ("online", "running", "True"):
        return "\U0001f7e2"
    if str(s) in ("degraded", "warning"):
        return "\U0001f7e1"
    if str(s) in ("offline", "error", "inactive"):
        return "\U0001f534"
    return "\u26aa"


def generate_system_canvas() -> Dict[str, Any]:
    logger.info("[CANVAS] Generando matriz vectorial...")
    kg = _load_json(RUTAS["grafo"]) or {"nodes": [], "edges": []}
    report = _load_json(RUTAS["reporte"]) or {}
    health = report.get("ecosystem_health", {}).get("nodes", {})

    nodos_raw = kg.get("nodes", [])
    aristas_raw = kg.get("edges", [])
    posiciones = _layout_circular(len(nodos_raw))

    vnodes = []
    for i, nd in enumerate(nodos_raw):
        nid = nd.get("id", f"n{i}")
        lbl = nd.get("label", nid)
        tp = nd.get("type", "default")
        st = health.get(lbl, nd.get("status", "unknown"))
        x, y = posiciones[i] if i < len(posiciones) else (CENTER_X, CENTER_Y)
        vnodes.append(
            {
                "id": nid,
                "label": lbl,
                "type": tp,
                "x": x,
                "y": y,
                "radius": NODE_RADIUS,
                "color": _color(tp),
                "status": st,
                "status_emoji": _emoji(str(st)),
                "opacity": 1.0 if str(st) in ("online", "running") else 0.4,
            }
        )

    pmap = {n["id"]: (n["x"], n["y"]) for n in vnodes}
    vedges = []
    for e in aristas_raw:
        s = e.get("source", e.get("from", ""))
        t = e.get("target", e.get("to", ""))
        sp, tp = pmap.get(s), pmap.get(t)
        if sp and tp:
            vedges.append(
                {
                    "source": s,
                    "target": t,
                    "x1": sp[0],
                    "y1": sp[1],
                    "x2": tp[0],
                    "y2": tp[1],
                    "color": "#44aaff",
                    "width": 2,
                }
            )

    bot = report.get("bot_strategy", {}).get("metrics", {})
    topics = report.get("market_analysis", {}).get("topics", [])
    sc = {}
    for n in vnodes:
        s = str(n["status"])
        sc[s] = sc.get(s, 0) + 1

    canvas = {
        "timestamp": datetime.utcnow().isoformat(),
        "canvas": {
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "center": {"x": CENTER_X, "y": CENTER_Y},
        },
        "nodes": vnodes,
        "edges": vedges,
        "overlays": {
            "total_nodes": len(vnodes),
            "status_summary": sc,
            "bot_hashrate": bot.get("hashrate", "N/A"),
            "bot_uptime": bot.get("uptime", "N/A"),
            "market_topics": topics[:3],
        },
    }

    os.makedirs(os.path.dirname(RUTAS["canvas"]) or ".", exist_ok=True)
    with open(RUTAS["canvas"], "w", encoding="utf-8") as f:
        json.dump(canvas, f, ensure_ascii=False, indent=2)

    _dispatch("system_canvas_update", canvas)
    logger.info(f"[CANVAS] {len(vnodes)} nodos, {len(vedges)} conexiones.")
    return canvas


def check_and_emit_critical_event() -> Optional[Dict[str, Any]]:
    prev = _load_json(RUTAS["canvas"])
    curr = generate_system_canvas()
    if not prev:
        return curr
    ps = {n["id"]: n["status"] for n in prev.get("nodes", [])}
    cs = {n["id"]: n["status"] for n in curr.get("nodes", [])}
    cambios = [f"{i}: {ps[i]}->{cs[i]}" for i in cs if i in ps and ps[i] != cs[i]]
    if cambios:
        logger.warning(f"[CANVAS] Cambios: {', '.join(cambios)}")
        _dispatch("system_canvas_update", curr)
    return curr


def export_svg(canvas: Optional[Dict[str, Any]] = None) -> str:
    if canvas is None:
        canvas = _load_json(RUTAS["canvas"]) or generate_system_canvas()
    w, h = canvas["canvas"]["width"], canvas["canvas"]["height"]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" style="background:#0a0a1a;font-family:monospace">',
        '<defs><filter id="g"><feGaussianBlur stdDeviation="3"/></filter></defs>',
    ]
    for e in canvas.get("edges", []):
        out.append(
            f'<line x1="{e["x1"]}" y1="{e["y1"]}" x2="{e["x2"]}" y2="{e["y2"]}" '
            f'stroke="{e["color"]}" stroke-width="{e["width"]}" opacity="0.6"/>'
        )
    for n in canvas.get("nodes", []):
        out.append(
            f'<circle cx="{n["x"]}" cy="{n["y"]}" r="{n["radius"]}" '
            f'fill="{n["color"]}" opacity="{n["opacity"]}" filter="url(#g)"/>'
        )
        out.append(
            f'<text x="{n["x"]}" y="{n["y"]+n["radius"]+16}" '
            f'text-anchor="middle" fill="#ccc" font-size="11">'
            f'{n["status_emoji"]} {n["label"]}</text>'
        )
    o = canvas.get("overlays", {})
    out.append(
        f'<text x="16" y="24" fill="#88aaff" font-size="14">'
        f'Nodos: {o.get("total_nodes",0)} | Hashrate: {o.get("bot_hashrate","N/A")}</text>'
    )
    out.append("</svg>")
    return "\n".join(out)


def run_canvas_update() -> Dict[str, Any]:
    return check_and_emit_critical_event()


def run_svg_export() -> str:
    svg = export_svg()
    with open("AURA_Core/system_map.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    logger.info(f"[CANVAS] SVG exportado ({len(svg)} chars)")
    return svg


if __name__ == "__main__":
    c = generate_system_canvas()
    print(json.dumps(c, indent=2)[:300], "...")
    s = run_svg_export()
    print(f"SVG: {len(s)} chars")
