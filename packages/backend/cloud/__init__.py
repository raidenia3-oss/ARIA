# -*- coding: utf-8 -*-
"""AURA OS — cloud package."""
from backend.cloud.firebase_manager import firebase_sync
from backend.cloud.offline_queue import offline_queue

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
