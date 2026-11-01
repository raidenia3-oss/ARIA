"""Paquete `training`.

Necesario para que pytest calcule los nombres de módulo `training.tests.*`.

Sin este archivo, `training/tests/__init__.py` existía pero `training/__init__.py`
no, así que pytest subía un solo nivel, usaba `training/` como basedir y
producía `tests.test_quality_filter` — que colisiona con el paquete `tests/`
de la raíz. Además prependaba `training/` a `sys.path`, y
`training/scripts/` (paquete real) tapaba al `scripts/` de la raíz, por lo que
`from scripts.post100_mission import ...` fallaba con ModuleNotFoundError.
"""
