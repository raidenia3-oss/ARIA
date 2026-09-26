import os
import sys
import py_compile
from pathlib import Path

ROOT = Path(__file__).parent
PY_FILES = list(ROOT.rglob("*.py"))

errors = []
ok = 0

for f in sorted(PY_FILES):
    try:
        py_compile.compile(str(f), doraise=True)
        ok += 1
    except py_compile.PyCompileError as e:
        errors.append((str(f), str(e)))
    except SyntaxError as e:
        errors.append((str(f), str(e)))

print(f"Checked {ok + len(errors)} files, {ok} OK, {len(errors)} errors")
for path, err in errors:
    print(f"ERROR in {path}:\n{err}\n")

if errors:
    sys.exit(1)
