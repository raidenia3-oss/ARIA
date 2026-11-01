# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from typing import Any, Dict
logger = logging.getLogger('ARIA.Memory')
class AriaMemory:
    def recall(self,q,**kw): return {'query':q,'results':[]}
    def remember(self,k,v): return {'ok':True,'key':k}
    def status(self): return {'ok':True}
