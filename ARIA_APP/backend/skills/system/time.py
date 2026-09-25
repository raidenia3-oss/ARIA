import os
from datetime import datetime
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    return {"time": now.strftime("%H:%M:%S"), "date": now.strftime("%d/%m/%Y")}
