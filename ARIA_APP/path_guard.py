import os
import sys
from pathlib import Path

ARIA_APP = Path(__file__).resolve().parent


class PathGuardError(PermissionError):
    pass


def _get_roots():
    roots_env = os.environ.get("ARIA_FS_ROOTS", "")
    if roots_env.strip():
        roots = [Path(p.strip()) for p in roots_env.split(os.pathsep) if p.strip()]
    else:
        roots = [ARIA_APP / "data" / "work"]
    resolved = []
    for r in roots:
        try:
            r.mkdir(parents=True, exist_ok=True)
            resolved.append(Path(os.path.realpath(str(r))))
        except Exception:
            continue
    if not resolved:
        fallback = ARIA_APP / "data" / "work"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
            resolved = [Path(os.path.realpath(str(fallback)))]
        except Exception:
            return []
    return resolved


def resolve_allowed(path, need="read"):
    if need not in ("read", "write"):
        raise PermissionError("denegado")
    if path is None:
        raise PermissionError("denegado")
    if not isinstance(path, (str, os.PathLike)):
        raise PermissionError("denegado")
    s = str(path)
    if s.strip() == "":
        raise PermissionError("denegado")
    if "\x00" in s:
        raise PermissionError("denegado")
    # UNC y prefijo \\?\
    if s.startswith("\\\\") or s.startswith("//"):
        raise PermissionError("denegado")
    # ADS: ':' solo como letra de unidad en posicion 1
    if ":" in s:
        # permitir solo "X:" al inicio
        ok_drive = (len(s) >= 2 and s[1] == ":" and s[0].isalpha()
                    and (len(s) == 2 or s[2] in ("\\", "/")))
        if not ok_drive:
            raise PermissionError("denegado")
        # ademas, no puede haber otro ':' mas adelante
        if s[2:].count(":") > 0:
            raise PermissionError("denegado")
    # segmentos que terminan en punto o espacio
    try:
        for part in Path(s).parts:
            if part in ("", ".", ".."):
                continue
            if part.endswith(" ") or part.endswith("."):
                raise PermissionError("denegado")
    except Exception:
        raise PermissionError("denegado")
    roots = _get_roots()
    if not roots:
        raise PermissionError("denegado")
    try:
        if os.path.isabs(s):
            cand = Path(os.path.realpath(s))
        else:
            cand = Path(os.path.realpath(str(roots[0] / s)))
    except Exception:
        raise PermissionError("denegado")
    cand_norm = os.path.normcase(str(cand))
    allowed = False
    for r in roots:
        r_norm = os.path.normcase(str(r))
        try:
            common = os.path.commonpath([cand_norm, r_norm])
        except ValueError:
            continue
        if os.path.normcase(common) == r_norm:
            if cand_norm == r_norm or cand_norm.startswith(r_norm + os.sep):
                allowed = True
                break
    if not allowed:
        raise PermissionError("denegado")
    # limite 1 MB
    try:
        if cand.exists() and cand.is_file():
            if cand.stat().st_size > 1024 * 1024:
                raise PermissionError("denegado")
    except PermissionError:
        raise
    except Exception:
        raise PermissionError("denegado")
    return str(cand)