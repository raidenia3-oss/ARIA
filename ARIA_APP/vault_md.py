# -*- coding: utf-8 -*-
"""ARIA - Vault en Markdown + backup seguro (idea de Obsidian como backend).

La memoria de ARIA (grafo, experiencia, auditoria) se ESPEJA a archivos .md legibles,
con split MAQUINA (lo que ARIA genera sola) vs HUMANO (lo que pone Daniel). Asi el
conocimiento es portable, legible y editable sin ARIA. Ademas: backup nocturno a un
destino PRIVADO/cifrado, para no perder el cerebro (tu vieja preocupacion).

  data/vault/maquina/  -> conocimiento.md, experiencia.md, auditoria.md  (auto)
  data/vault/humano/   -> perfil.md, notas.md                            (los editas tu)

Seguridad: el backup puede ir CIFRADO (clave) para dejarlo en USB o repo privado sin
exponer datos. NUNCA subas el vault en claro a un repo publico. 100% local, Regla v2.
La composicion del md (_md_*) y el cifrado son testeables.
"""
import os
import io
import json
import time
import zipfile

_DIR = os.path.dirname(os.path.abspath(__file__))
_VAULT = os.path.join(_DIR, "data", "vault")
_MAQ = os.path.join(_VAULT, "maquina")
_HUM = os.path.join(_VAULT, "humano")
# archivos de memoria a respaldar (ademas del vault .md)
_MEMORIA = ["data/experience.md", "data/experience.jsonl", "data/conocimiento.db",
            "data/aprendizaje.db", "data/forma.json", "data/vault.dat"]


def _escribir(ruta, texto):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)


def _md_conocimiento(grafo):
    """Markdown del grafo: proposiciones agrupadas por tema."""
    lineas = ["# Conocimiento de ARIA", "", "_Espejo auto-generado del grafo._", ""]
    try:
        db = grafo._conn()
        filas = db.execute("SELECT texto, tema FROM nodos ORDER BY tema").fetchall()
    except Exception:
        filas = []
    por_tema = {}
    for texto, tema in filas:
        por_tema.setdefault(tema or "general", []).append(texto)
    for tema in sorted(por_tema):
        lineas.append("## %s" % tema)
        for t in por_tema[tema]:
            lineas.append("- %s" % t)
        lineas.append("")
    if not filas:
        lineas.append("_(vacio)_")
    return "\n".join(lineas)


def _md_experiencia():
    lineas = ["# Lecciones de ARIA", "", "_Que funciono / que fallo._", ""]
    try:
        import experiencia
        for x in experiencia.leer(n=100):
            ic = {"exito": "OK", "fallo": "X", "nota": "~"}.get(x.get("resultado"), "~")
            lineas.append("- [%s] **%s** (%s): %s" % (ic, x.get("fecha", ""),
                          x.get("tema", "general"), x.get("leccion", "")))
    except Exception:
        lineas.append("_(sin experiencia)_")
    return "\n".join(lineas)


def _md_auditoria():
    lineas = ["# Auditoria de ARIA", "", "_Resumen de acciones._", ""]
    try:
        import auditoria
        r = auditoria.resumen()
        lineas.append("- total: %s" % r.get("total"))
        lineas.append("- autonomas: %s | pedidas: %s" % (r.get("autonomas"), r.get("pedidas")))
        lineas.append("- por tipo: %s" % json.dumps(r.get("por_tipo", {}), ensure_ascii=False))
    except Exception:
        lineas.append("_(sin auditoria)_")
    return "\n".join(lineas)


def exportar(grafo=None):
    """Espeja la memoria a .md (lado MAQUINA) y asegura las plantillas del lado HUMANO."""
    if grafo is None:
        try:
            import conocimiento
            grafo = conocimiento.grafo()
        except Exception:
            grafo = None
    if grafo is not None:
        _escribir(os.path.join(_MAQ, "conocimiento.md"), _md_conocimiento(grafo))
    _escribir(os.path.join(_MAQ, "experiencia.md"), _md_experiencia())
    _escribir(os.path.join(_MAQ, "auditoria.md"), _md_auditoria())
    # lado humano: no sobrescribir lo que escribio Daniel
    for nombre, plantilla in (("perfil.md", "# Perfil (lo escribe Daniel)\n\n- "),
                              ("notas.md", "# Notas de Daniel\n\n- ")):
        ruta = os.path.join(_HUM, nombre)
        if not os.path.isfile(ruta):
            _escribir(ruta, plantilla)
    return {"ok": True, "maquina": _MAQ, "humano": _HUM}


# ---------------------------------------------------------------- backup
def _derivar(clave, salt):
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    import base64
    kdf = Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1)
    return base64.urlsafe_b64encode(kdf.derive(clave.encode("utf-8")))


def _zip_memoria():
    """Crea en memoria un zip con el vault .md + los archivos de memoria. Devuelve bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(_VAULT):
            for fn in files:
                ruta = os.path.join(base, fn)
                z.write(ruta, os.path.relpath(ruta, _DIR))
        for rel in _MEMORIA:
            ruta = os.path.join(_DIR, rel)
            if os.path.isfile(ruta):
                z.write(ruta, rel)
    return buf.getvalue()


def respaldar(destino=None, clave=None):
    """Backup del vault + memoria a un .zip (o .zip.enc si das clave) con fecha.
    destino: carpeta (USB, repo privado...). Por defecto data/backups/."""
    datos = _zip_memoria()
    cifrado = bool(clave)
    if cifrado:
        try:
            from cryptography.fernet import Fernet
            import os as _os
            salt = _os.urandom(16)
            token = Fernet(_derivar(clave, salt)).encrypt(datos)
            datos = salt + token          # salt al frente para descifrar luego
        except Exception as exc:
            return {"error": "cifrado fallo (falta cryptography?): %s" % exc}
    destino = destino or os.path.join(_DIR, "data", "backups")
    os.makedirs(destino, exist_ok=True)
    nombre = "aria_backup_%s.zip%s" % (time.strftime("%Y%m%d_%H%M"), ".enc" if cifrado else "")
    ruta = os.path.join(destino, nombre)
    try:
        with open(ruta, "wb") as f:
            f.write(datos)
    except Exception as exc:
        return {"error": str(exc)}
    return {"ok": True, "archivo": ruta, "cifrado": cifrado, "bytes": len(datos)}


def restaurar(ruta_backup, destino, clave=None):
    """Restaura un backup (.zip o .zip.enc). Extrae en 'destino'."""
    try:
        with open(ruta_backup, "rb") as f:
            datos = f.read()
    except Exception as exc:
        return {"error": str(exc)}
    if ruta_backup.endswith(".enc"):
        if not clave:
            return {"error": "backup cifrado: falta clave"}
        try:
            from cryptography.fernet import Fernet
            salt, token = datos[:16], datos[16:]
            datos = Fernet(_derivar(clave, salt)).decrypt(token)
        except Exception:
            return {"error": "clave incorrecta o backup corrupto"}
    try:
        os.makedirs(destino, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            z.extractall(destino)
    except Exception as exc:
        return {"error": str(exc)}
    return {"ok": True, "destino": destino}


def tarea_nocturna(grafo=None, destino=None, clave=None):
    """Lo que corre cada noche: espeja a .md + respalda (cifrado si hay clave)."""
    exportar(grafo)
    return respaldar(destino, clave)
