"""Diagnóstico temporal: replica el setup de rutas de standalone.py."""
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
app_dir = Path(HERE).resolve()
base = app_dir
project_root = app_dir.parent

os.chdir(app_dir)
for p in [str(app_dir / "backend"), str(project_root), str(app_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

print("argv[0]      :", sys.argv[0])
print("CWD          :", os.getcwd())
print("app_dir      :", app_dir)
print("project_root :", project_root)
print("sys.path[0:6]:")
for i, p in enumerate(sys.path[:6]):
    print("   ", i, repr(p))

import backend
print("backend.__file__ :", backend.__file__)
print("backend.__path__ :")
for p in list(backend.__path__)[:6]:
    print("    ", p)

try:
    import backend.agent
    print("backend.agent ->", backend.agent.__file__)
    print("   tiene core.py?", (Path(backend.agent.__file__).parent / "core.py").exists())
except Exception as e:
    print("backend.agent ERROR:", e)

try:
    print("backend.agent.core: IMPORT OK")
except Exception as e:
    print("backend.agent.core ERROR:", type(e).__name__, e)

try:
    print("backend.daemon.cross_device_sync: IMPORT OK")
except Exception as e:
    print("backend.daemon ERROR:", type(e).__name__, e)