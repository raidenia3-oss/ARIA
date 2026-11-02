# -*- coding: utf-8 -*-
"""ARIA - Pruebas de la capa social + conocimiento + experiencia + mejora.

Corre: ./.venv/Scripts/python.exe test_capa_social.py
(o con pytest). La memoria semantica se APAGA en los tests para no depender de red.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import social_skills as ss
import social_sandbox as sb
import conocimiento as C
import experiencia as E
import mejora as M
import aprendizaje as A
import planificador as PL
import nucleo as N
import forma as F
import presencia as PR
import autonomia_guardia as AG
import conversacion as CV
import social_rolemodels as RM
import cita_sim as CS


# ---------------------------------------------------------------- social_skills
def test_deteccion_sin_falsos_positivos():
    assert ss.detect_emotions("dame la consola") == []          # 'solo' NO dentro de 'consola'
    assert "loneliness" in ss.detect_emotions("me siento solo")
    assert "sadness" in ss.detect_emotions("estoy muy triste hoy")

def test_detecta_multiples_emociones():
    e = ss.detect_emotions("estoy triste y ansioso")
    assert "sadness" in e and "anxiety" in e

def test_todas_las_emociones_tienen_hint():
    for emo in list(ss.EMOTION_KEYWORDS.keys()) + ["neutral"]:
        assert ss.get_conversation_hint(emo), "falta hint para %s" % emo

def test_analysis_estructura():
    a = ss.social_analysis("gracias, me ayudaste")
    assert a["emotion"] == "gratitude" and "principle" in a and "emotions" in a

def test_negacion_no_cuenta():
    assert "sadness" not in ss.detect_emotions("no estoy triste hoy")
    assert "sadness" in ss.detect_emotions("estoy triste hoy")

def test_intensidad():
    assert ss.intensidad("estoy triste") < ss.intensidad("estoy MUY triste!!!")

def test_registro_casual_vs_formal():
    assert ss.registro("jaja causa que tal") == "casual"
    assert ss.registro("Buenas tardes, quisiera consultar algo") == "formal"

def test_analysis_emocion_fuerte_marca_hint():
    a = ss.social_analysis("estoy MUY enojado!!!")
    assert a["intensidad"] >= 0.6 and "FUERTE" in a["hint"]


# ---------------------------------------------------------------- social_sandbox
def test_evaluar_buena_vs_aduladora():
    esc = {"persona": "amigo", "situacion": "mala noticia", "emocion": "sadness",
           "mensaje_usuario": "Hoy fue un dia horrible, siento que nada me sale."}
    buena = "Entiendo que te sientas asi despues de un dia horrible. Que fue lo que paso?"
    mala = "Obvio, tienes toda la razon, a por todo!"
    assert sb.evaluar(esc, buena)["puntaje"] > sb.evaluar(esc, mala)["puntaje"]

def test_practicar_memoria_off():
    r = sb.practicar(lambda t: "Entiendo como te sientes. Que paso exactamente?",
                     n=3, guardar=False, usar_memoria=False)
    assert r["ok"] and r["n"] == 3 and 0.0 <= r["promedio"] <= 1.0

def test_consejo_para_emocion():
    assert C  # modulo cargado
    assert sb.consejo_para("anger")["id"] == "de_escalada"


# ---------------------------------------------------------------- conocimiento
def _grafo_tmp():
    g = C.Grafo(os.path.join(tempfile.mkdtemp(), "c.db"))
    g._sem_intentado = True   # apaga semantica (sin red)
    return g

def test_grafo_aprende_y_relaciona():
    g = _grafo_tmp()
    a = g.aprender("un Transformer usa auto-atencion", tema="llm", auto=False)
    b = g.aprender("la auto-atencion pondera tokens", tema="llm", auto=False)
    assert g.conectar(a, b, "usa")
    rel = g.relacionados(a)
    assert any("pondera" in x["texto"] for x in rel)

def test_grafo_cadena_razonamiento():
    g = _grafo_tmp()
    a = g.aprender("A", auto=False); b = g.aprender("B", auto=False); c = g.aprender("C", auto=False)
    g.conectar(a, b, "lleva"); g.conectar(b, c, "lleva")
    cadena = g.cadena(a, profundidad=2)
    textos = [x["texto"] for x in cadena]
    assert "B" in textos and "C" in textos    # recorre A->B->C

def test_grafo_dedupe_y_stats():
    g = _grafo_tmp()
    g.aprender("repetida", auto=False); g.aprender("repetida", auto=False)
    assert g.stats()["nodos"] == 1          # no duplica

def test_grafo_export_dot():
    g = _grafo_tmp()
    a = g.aprender("X", tema="t", auto=False); b = g.aprender("Y", tema="t", auto=False)
    g.conectar(a, b, "r")
    dot = g.exportar_dot("t")
    assert dot.startswith("digraph") and "->" in dot


# ---------------------------------------------------------------- experiencia
def _exp_tmp():
    d = tempfile.mkdtemp()
    E._DATA = d
    E._MD = os.path.join(d, "experience.md")
    E._JSONL = os.path.join(d, "experience.jsonl")
    E._SEM_CACHE = None     # apaga semantica
    return d

def test_experiencia_registra_y_lee():
    _exp_tmp()
    assert E.registrar("rembg evita fondos opacos", "chibi", "exito", "avatar")["ok"]
    assert E.registrar("intervalo fijo = patron bot", "rollercoin", "fallo", "auto")["ok"]
    assert len(E.leer()) == 2
    assert len(E.leer(solo="fallo")) == 1

def test_experiencia_relevantes_por_palabra():
    _exp_tmp()
    E.registrar("el fondo del sprite debe recortarse con rembg", "chibi", "exito", "avatar")
    rel = E.relevantes("problema con el fondo del sprite")
    assert any("rembg" in r["leccion"] for r in rel)

def test_experiencia_resumen():
    _exp_tmp()
    E.registrar("a", "", "exito"); E.registrar("b", "", "fallo")
    r = E.resumen()
    assert r["total"] == 2 and r["exitos"] == 1 and r["fallos"] == 1


# ---------------------------------------------------------------- mejora (propose-probe)
def _mejora_tmp():
    d = tempfile.mkdtemp()
    M._PEND = os.path.join(d, "pending")
    M._APLIC = os.path.join(d, "aplicadas")
    M._SKILLS = os.path.join(d, "skills")
    return d

SKILL_BUENA = (
    "SKILL_ENABLED = True\n"
    "def match(texto):\n    return 'hola' in texto.lower()\n"
    "def run(texto):\n    return {'response': 'hola!'}\n"
)
SKILL_PELIGROSA = (
    "SKILL_ENABLED = True\n"
    "import subprocess\n"
    "def match(t):\n    return True\n"
    "def run(t):\n    subprocess.Popen(['calc'])\n    return {}\n"
)

def test_probe_acepta_skill_valida():
    _mejora_tmp()
    pid = M.proponer("skill", SKILL_BUENA, "saluda", "saludo")["id"]
    v = M.probar(pid)
    assert v["ok"] and v["veredicto"] == "aprobable"

def test_probe_rechaza_skill_peligrosa():
    _mejora_tmp()
    pid = M.proponer("skill", SKILL_PELIGROSA, "mala", "mala")["id"]
    v = M.probar(pid)
    assert not v["ok"] and any("subprocess" in p for p in v["problemas"])

def test_probe_rechaza_sintaxis_mala():
    _mejora_tmp()
    pid = M.proponer("skill", "def match( : pass", "rota")["id"]
    v = M.probar(pid)
    assert not v["ok"]

def test_aprobar_requiere_probe_ok():
    _mejora_tmp()
    pid = M.proponer("skill", SKILL_PELIGROSA, "mala")["id"]
    r = M.aprobar(pid)                     # debe NEGARSE (fail-closed)
    assert "error" in r

def test_aprobar_aplica_skill_buena():
    _mejora_tmp()
    pid = M.proponer("skill", SKILL_BUENA, "saluda", "saludo_test")["id"]
    r = M.aprobar(pid)
    assert r.get("ok") and os.path.isfile(r["aplicado"])
    assert M.listar("pendiente") == []     # ya no esta pendiente

def test_rechazar_mueve_fuera_de_pendiente():
    _mejora_tmp()
    pid = M.proponer("skill", SKILL_BUENA, "x")["id"]
    M.rechazar(pid, "no la quiero")
    assert M.listar("pendiente") == []


# ---------------------------------------------------------------- aprendizaje (arnes)
def _arnes_tmp():
    ar = A.Arnes(responder=None, db_path=os.path.join(tempfile.mkdtemp(), "a.db"))
    ar._grafo = False   # evita cargar conocimiento/semantica en el test
    return ar

def test_ensenar_tres_fases():
    ar = _arnes_tmp()
    r = ar.ensenar("auto-atencion", tema="llm")
    assert r["ok"]
    assert set(r["fases"].keys()) == {"predecir", "explicar", "verificar"}
    assert ar.dominio("auto-atencion") == 0.0     # recien creado, sin practica

def test_dominio_sube_con_aciertos():
    ar = _arnes_tmp()
    ar.ensenar("backprop", tema="llm")
    ar.registrar_resultado("backprop", True)
    ar.registrar_resultado("backprop", True)
    ar.registrar_resultado("backprop", False)
    assert ar.dominio("backprop") == round(2/3, 2)

def test_pista_adaptativa():
    ar = _arnes_tmp()
    ar.ensenar("gradiente", tema="llm")
    assert ar.nivel_pista("gradiente") == 3        # dominio 0 -> pista fuerte
    for _ in range(5):
        ar.registrar_resultado("gradiente", True)
    assert ar.nivel_pista("gradiente") == 0        # dominado -> sin pista

def test_lagunas_detecta_debiles():
    ar = _arnes_tmp()
    ar.ensenar("debil", tema="t"); ar.ensenar("fuerte", tema="t")
    ar.registrar_resultado("debil", False)
    for _ in range(4):
        ar.registrar_resultado("fuerte", True)
    lag = [x["proposicion"] for x in ar.lagunas(tema="t")]
    assert "debil" in lag and "fuerte" not in lag

def test_practicar_devuelve_pista_acorde():
    ar = _arnes_tmp()
    ar.ensenar("tema1", tema="t")
    p = ar.practicar("tema1", tema="t")
    assert p["nivel_pista"] == 3 and "tema1" in p["prompt"]

def test_resumen_cuenta_dominados():
    ar = _arnes_tmp()
    ar.ensenar("c1"); ar.ensenar("c2")
    for _ in range(5):
        ar.registrar_resultado("c1", True)
    r = ar.resumen()
    assert r["conceptos"] == 2 and r["dominados"] == 1


# ---------------------------------------------------------------- planificador (NCM)
def test_planificador_corto_una_pasada():
    llamadas = []
    def resp(t): llamadas.append(t); return "respuesta corta"
    r = PL.responder_estructurado(resp, "hola que tal")
    assert r["modo"] == "directo" and len(llamadas) == 1

def test_planificador_largo_dos_pasadas():
    def resp(t): return "- punto uno\n- punto dos\n- punto tres"
    r = PL.responder_estructurado(resp, "explicame como funciona un transformer")
    assert r["modo"] == "estructurado"
    assert len(r["boceto"]) == 3 and "1)" in r["respuesta"]

def test_es_largo_heuristica():
    assert PL.es_largo("explica la fotosintesis")
    assert not PL.es_largo("ok gracias")


# ---------------------------------------------------------------- nucleo (visual, matematica pura)
def test_espirografo_normalizado():
    pts = N._espirografo(220, 68, 110, vueltas=4, n=100)
    assert len(pts) == 101
    assert all(-1.01 <= x <= 1.01 and -1.01 <= y <= 1.01 for x, y in pts)

def test_nucleo_importa_sin_pantalla():
    # el modulo carga aunque PyQt5 no este; crear_nucleo existe
    assert hasattr(N, "crear_nucleo")

def test_reaccion_al_mouse():
    # cursor encima -> cercania alta, sin inclinacion
    prox, lx, ly = N._reaccion(100, 100, 100, 100)
    assert prox > 0.95 and abs(lx) < 0.01 and abs(ly) < 0.01
    # cursor lejos -> cercania 0
    prox2, _, _ = N._reaccion(100, 100, 5000, 5000)
    assert prox2 == 0.0
    # cursor a la derecha -> se inclina a la derecha (lx>0)
    _, lx3, _ = N._reaccion(100, 100, 180, 100)
    assert lx3 > 0

def test_modo_ventana_presencia():
    # mouse cerca -> pasa al frente de inmediato
    modo, idle = N._decidir_modo(0.9, "fondo", 0)
    assert modo == "frente" and idle == 0
    # lejos pero poco rato -> sigue como estaba (histeresis)
    modo, idle = N._decidir_modo(0.0, "frente", 0)
    assert modo == "frente" and idle == 1
    # lejos suficiente rato -> cae a fondo (segundo plano)
    modo, idle = N._decidir_modo(0.0, "frente", 90)
    assert modo == "fondo"


# ---------------------------------------------------------------- mejora hotload
def test_hotload_llama_reload():
    _mejora_tmp()
    pid = M.proponer("skill", SKILL_BUENA, "saluda", "saludo_hot")["id"]
    marca = {"recargado": False}
    def reload_fn():
        marca["recargado"] = True
        return ["saludo_hot"]
    r = M.aprobar(pid, reload_fn=reload_fn)
    assert r.get("ok") and marca["recargado"] and r["hotload"] == ["saludo_hot"]


# ---------------------------------------------------------------- forma (nucleo/avatar)
class _Cuerpo:
    def __init__(self): self.visible = False
    def show(self): self.visible = True
    def hide(self): self.visible = False

def _forma_tmp():
    n, a = _Cuerpo(), _Cuerpo()
    fm = F.Forma(nucleo_factory=lambda: n, avatar_factory=lambda: a,
                 config_path=os.path.join(tempfile.mkdtemp(), "forma.json"),
                 por_defecto="nucleo")
    return fm, n, a

def test_forma_mostrar_nucleo_oculta_avatar():
    fm, n, a = _forma_tmp()
    fm.mostrar("nucleo")
    assert n.visible and not a.visible and fm.actual == "nucleo"

def test_forma_alternar():
    fm, n, a = _forma_tmp()
    fm.mostrar("nucleo")
    fm.alternar()
    assert a.visible and not n.visible and fm.actual == "avatar"

def test_forma_ambos_y_oculto():
    fm, n, a = _forma_tmp()
    fm.mostrar("ambos"); assert n.visible and a.visible
    fm.mostrar("oculto"); assert not n.visible and not a.visible

def test_forma_auto_por_estado():
    fm, n, a = _forma_tmp()
    fm.auto("pensando"); assert fm.actual == "nucleo"
    fm.auto("conversando"); assert fm.actual == "avatar"

def test_forma_auto_idle_usa_preferida():
    fm, n, a = _forma_tmp()
    fm.mostrar("avatar")          # preferida = avatar
    fm.auto("idle")
    assert fm.actual == "avatar"

def test_forma_persiste():
    d = tempfile.mkdtemp(); cfg = os.path.join(d, "forma.json")
    f1 = F.Forma(config_path=cfg, por_defecto="nucleo")
    f1.mostrar("avatar")
    f2 = F.Forma(config_path=cfg, por_defecto="nucleo")
    assert f2.actual == "avatar"   # recordo entre 'sesiones'


# ---------------------------------------------------------------- presencia
def test_presencia_clasifica():
    assert PR._clasificar(5, umbral_ausente=120) == "activo"
    assert PR._clasificar(200, umbral_ausente=120) == "ausente"

def test_presencia_transicion_con_histeresis():
    # activo -> ausente al pasar el umbral
    assert PR._transicion("activo", 130, 120) == "ausente"
    # ausente -> sigue ausente si la inactividad apenas baja un poco
    assert PR._transicion("ausente", 60, 120, margen=10) == "ausente"
    # ausente -> activo solo con actividad reciente (inactividad < margen)
    assert PR._transicion("ausente", 3, 120, margen=10) == "activo"

def test_vigia_dispara_callbacks_en_transicion():
    eventos = []
    v = PR.Vigia(on_activo=lambda: eventos.append("activo"),
                 on_ausente=lambda: eventos.append("ausente"), umbral_ausente=120)
    v._estado = "activo"
    # forzar inactividad alta -> transicion a ausente
    import presencia as _pr
    orig = _pr.inactividad_segundos
    _pr.inactividad_segundos = lambda: 999
    try:
        v.paso()
    finally:
        _pr.inactividad_segundos = orig
    assert eventos == ["ausente"]


# ---------------------------------------------------------------- guardia de autonomia
def test_guardia_clasifica():
    assert AG._clasificar("file_read", {"path": "x"}) == "auto"       # leer -> solo
    assert AG._clasificar("system_status", {}) == "auto"
    assert AG._clasificar("file_write", {"path": "x"}) == "aprobar"   # escribir -> OK
    assert AG._clasificar("skill_desconocida", {}) == "aprobar"       # fail-safe
    # palabra destructiva en params aunque la skill parezca safe
    assert AG._clasificar("note_add", {"texto": "borra todo rm -rf"}) == "aprobar"

def test_guardia_auto_ejecuta():
    r = AG.guard("file_read", {"path": "x"}, ejecutar=lambda: "leido")
    assert r.get("ok") and r["resultado"] == "leido"

def test_guardia_irreversible_encola_no_ejecuta():
    _ag_tmp()
    corrio = {"v": False}
    r = AG.guard("file_write", {"path": "y"}, ejecutar=lambda: corrio.__setitem__("v", True))
    assert "pendiente" in r and corrio["v"] is False     # NO corrio sola
    assert len(AG.listar()) == 1

def test_guardia_aprobar_ejecuta():
    _ag_tmp()
    corrio = {"v": False}
    r = AG.guard("file_write", {"path": "y"}, ejecutar=lambda: corrio.__setitem__("v", True))
    pid = r["pendiente"]
    AG.aprobar(pid, ejecutar=lambda: corrio.__setitem__("v", True))
    assert corrio["v"] is True and AG.listar() == []

def _ag_tmp():
    d = tempfile.mkdtemp()
    AG._PEND = os.path.join(d, "pending")
    AG._HECHO = os.path.join(d, "hechas")


# ---------------------------------------------------------------- conversacion (continuidad)
def test_tendencia_empeora_y_mejora():
    assert CV._tendencia([0.5, 0.4, -0.6, -0.8]) == "empeora"
    assert CV._tendencia([-0.7, -0.5, 0.4, 0.6]) == "mejora"
    assert CV._tendencia([0.1, 0.0, 0.1]) == "estable"

def test_conversacion_registra_y_contexto():
    c = CV.crear_conversacion()
    c.registrar("estoy triste hoy")
    c.registrar("todo me sale mal, MUY mal!!!")
    ctx = c.contexto()
    assert ctx["emocion_dominante"] == "sadness" and ctx["turnos"] == 2
    assert "guia" in ctx and ctx["tendencia"] in ("empeora", "estable", "mejora")

def test_conversacion_registro_casual():
    c = CV.crear_conversacion()
    c.registrar("jaja causa todo bien")
    c.registrar("q tal nomas")
    assert c.registro() == "casual"


# ---------------------------------------------------------------- rolemodels + cita sim
def test_rolemodels_principios_y_no_hacer():
    assert len(RM.principios()) >= 6
    assert any("manipular" in x for x in RM.no_hacer())      # la linea roja esta
    assert RM.lecciones("respeto")                           # base de respeto existe

def test_cita_respeto_premia_pregunta_sin_presion():
    ev = CS.evaluar_mensaje("Me caiste bien, que te gusta hacer?", mood="receptiva")
    assert ev["criterios"]["respeto"] and ev["criterios"]["pregunta_genuina"]
    assert ev["puntaje"] >= 0.75

def test_cita_penaliza_insistir_ante_desinteres():
    ev = CS.evaluar_mensaje("dale pues no seas asi, dame tu numero ya", mood="cortante")
    assert not ev["criterios"]["respeto"]
    assert ev["criterios"].get("lee_el_desinteres") is False
    assert ev["puntaje"] < 0.5

def test_cita_premia_retirada_con_gracia():
    ev = CS.evaluar_mensaje("Veo que estas ocupada, sin presion, que te vaya bien :)", mood="ocupada")
    assert ev["criterios"].get("lee_el_desinteres") is True
    assert ev["puntaje"] >= 0.5

def test_cita_turno_devuelve_coaching():
    t = CS.turno("hola, que tal tu dia?", mood="receptiva", registrar_leccion=False)
    assert "respuesta_cita" in t and "coaching" in t and "feedback" in t["coaching"]


# ---------------------------------------------------------------- runner manual
def _run_all():
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn()
            print("  OK  %s" % fn.__name__)
            ok += 1
        except Exception:
            print("  FALLO %s" % fn.__name__)
            traceback.print_exc()
    print("\n%d/%d pruebas pasaron" % (ok, len(fns)))
    return ok == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
