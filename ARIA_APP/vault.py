# -*- coding: utf-8 -*-
"""ARIA - Boveda cifrada local (secretos: tokens, logins, llaves).

Regla v2: 100% local, sin servidor, sin red, sin puerto. Un solo archivo cifrado
en disco (data/vault.dat). Cifrado REAL: cryptography.Fernet (AES-128-CBC + HMAC-
SHA256). La llave se deriva de tu CONTRASENA MAESTRA con scrypt (lento a proposito,
anti fuerza-bruta). Nunca se guarda la contrasena ni los secretos en claro.

Aqui viven: ARIA_DISCORD_TOKEN, HF_TOKEN, login de Instagram, etc. -> reemplaza al
.env en texto plano (que path_guard justamente bloquea por riesgoso).

Fail-closed:
  - contrasena incorrecta  -> no abre (el HMAC de Fernet detecta la manipulacion)
  - archivo corrupto/ausente-> error claro, no "abre vacio por si acaso"

API:
  v = Vault()                      # usa data/vault.dat por defecto
  v.crear("mi_master")             # primera vez (crea la boveda vacia)
  v.abrir("mi_master")             # desbloquea en memoria
  v.set("ARIA_DISCORD_TOKEN", "...")
  v.get("ARIA_DISCORD_TOKEN")      # None si no esta
  v.listar()                       # SOLO nombres de claves (nunca valores)
  v.borrar("clave")
  v.cambiar_master("nueva")
  v.exportar_entorno()             # vuelca a os.environ (para discord/hf/etc.)
  v.cerrar()                       # limpia secretos de memoria
"""
import os
import json
import base64
import time


def disponible():
    try:
        import cryptography  # noqa
        return True
    except Exception:
        return False


_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_DEFECTO = os.path.join(_DIR, "vault.dat")

# parametros scrypt (coste CPU/memoria). n alto = mas lento = mas seguro.
_SCRYPT_N = 2 ** 17
_SCRYPT_R = 8
_SCRYPT_P = 1


def _derivar_llave(master, salt):
    """master (str) + salt (bytes) -> llave Fernet (base64 urlsafe de 32 bytes)."""
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    raw = kdf.derive(master.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


class Vault:
    def __init__(self, ruta=None):
        self.ruta = ruta or _DEFECTO
        self._secretos = None     # dict en memoria cuando esta abierta
        self._fernet = None
        self._salt = None
        self._abierta_en = 0.0
        self._ultimo_uso = 0.0
        self._auto_lock_segundos = 0

    # ---------------------------------------------------------- estado
    def existe(self):
        return os.path.isfile(self.ruta)

    def abierta(self):
        return self._secretos is not None

    # ---------------------------------------------------------- crear / abrir
    def crear(self, master, sobrescribir=False):
        """Crea una boveda vacia cifrada con la contrasena maestra."""
        if not disponible():
            return {"error": "falta 'cryptography' (pip install cryptography)"}
        if not master or len(master) < 4:
            return {"error": "contrasena muy corta (minimo 4)"}
        if self.existe() and not sobrescribir:
            return {"error": "ya existe una boveda; usa abrir() o sobrescribir=True"}
        self._salt = os.urandom(16)
        self._fernet = self._nuevo_fernet(master, self._salt)
        self._secretos = {}
        self._abierta_en = time.time()
        self._ultimo_uso = time.time()
        return self._guardar()

    def abrir(self, master):
        """Desbloquea la boveda en memoria. Fail-closed si la contrasena es mala."""
        if not disponible():
            return {"error": "falta 'cryptography' (pip install cryptography)"}
        if not self.existe():
            return {"error": "no hay boveda; crea una con crear()"}
        try:
            with open(self.ruta, "rb") as f:
                blob = json.loads(f.read().decode("utf-8"))
            self._salt = base64.b64decode(blob["salt"])
            token = base64.b64decode(blob["token"])
        except Exception as exc:
            return {"error": "boveda ilegible/corrupta: %s" % exc}
        try:
            from cryptography.fernet import Fernet, InvalidToken
            self._fernet = Fernet(_derivar_llave(master, self._salt))
            claro = self._fernet.decrypt(token)          # HMAC valida la contrasena
            self._secretos = json.loads(claro.decode("utf-8"))
        except Exception:
            # contrasena incorrecta o manipulacion -> fail-closed
            self._fernet = None
            self._secretos = None
            return {"error": "contrasena incorrecta o boveda alterada"}
        self._abierta_en = time.time()
        self._ultimo_uso = time.time()
        return {"ok": True, "claves": len(self._secretos)}

    def _nuevo_fernet(self, master, salt):
        from cryptography.fernet import Fernet
        return Fernet(_derivar_llave(master, salt))

    # ---------------------------------------------------------- operaciones
    def _check(self):
        if not self.abierta():
            raise RuntimeError("boveda cerrada; abre() primero")

    def set(self, clave, valor):
        try:
            self._check()
        except Exception as exc:
            return {"error": str(exc)}
        self._secretos[str(clave)] = str(valor)
        self._ultimo_uso = time.time()
        return self._guardar()

    def get(self, clave, defecto=None):
        if not self.abierta():
            return defecto
        if self.abierta():
            self._ultimo_uso = time.time()
        return self._secretos.get(str(clave), defecto) if self.abierta() else defecto

    def borrar(self, clave):
        try:
            self._check()
        except Exception as exc:
            return {"error": str(exc)}
        self._secretos.pop(str(clave), None)
        return self._guardar()

    def listar(self):
        """SOLO nombres de claves (jamas valores)."""
        if not self.abierta():
            return []
        return sorted(self._secretos.keys())

    def cambiar_master(self, nueva):
        """Re-cifra todo con una nueva contrasena maestra (nuevo salt)."""
        try:
            self._check()
        except Exception as exc:
            return {"error": str(exc)}
        if not nueva or len(nueva) < 4:
            return {"error": "contrasena muy corta (minimo 4)"}
        self._salt = os.urandom(16)
        self._fernet = self._nuevo_fernet(nueva, self._salt)
        return self._guardar()

    def exportar_entorno(self, solo=None):
        """Vuelca secretos a os.environ (para discord/hf/etc.). 'solo' = lista de
        claves a exportar; None = todas. Devuelve cuantas exporto."""
        if not self.abierta():
            return {"error": "boveda cerrada"}
        n = 0
        for k, v in self._secretos.items():
            if solo and k not in solo:
                continue
            os.environ[k] = v
            n += 1
        self._ultimo_uso = time.time()
        return {"ok": True, "exportadas": n}

    # ---------------------------------------------------------- persistencia
    def _guardar(self):
        if self._fernet is None or self._secretos is None:
            return {"error": "boveda no inicializada"}
        try:
            claro = json.dumps(self._secretos, ensure_ascii=False).encode("utf-8")
            token = self._fernet.encrypt(claro)
            blob = {"salt": base64.b64encode(self._salt).decode(),
                    "token": base64.b64encode(token).decode(),
                    "v": 1, "ts": time.time()}
            os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
            tmp = self.ruta + ".tmp"
            with open(tmp, "wb") as f:
                f.write(json.dumps(blob).encode("utf-8"))
            os.replace(tmp, self.ruta)   # escritura atomica
            return {"ok": True, "claves": len(self._secretos)}
        except Exception as exc:
            return {"error": "no pude guardar: %s" % exc}

    def configurar_auto_bloqueo(self, segundos):
        try:
            self._auto_lock_segundos = max(0, int(segundos))
        except Exception:
            self._auto_lock_segundos = 0
        return {"ok": True, "segundos": self._auto_lock_segundos}

    def auto_bloquear_si_inactivo(self):
        if not self.abierta() or not self._auto_lock_segundos:
            return {"ok": False, "bloqueada": False}
        if time.time() - self._ultimo_uso >= self._auto_lock_segundos:
            self.cerrar()
            return {"ok": True, "bloqueada": True}
        return {"ok": True, "bloqueada": False}

    def cerrar(self):
        """Limpia los secretos de memoria (bloquea la boveda)."""
        if isinstance(self._secretos, dict):
            self._secretos.clear()
        self._secretos = None
        self._fernet = None
        return {"ok": True}
