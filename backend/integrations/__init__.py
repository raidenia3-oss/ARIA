# -*- coding: utf-8 -*-
"""AURA OS - IDE & External Tool Integrations."""
from backend.integrations.ide_controller import IDEController, get_ide_controller

__all__ = ["IDEController", "get_ide_controller"]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
