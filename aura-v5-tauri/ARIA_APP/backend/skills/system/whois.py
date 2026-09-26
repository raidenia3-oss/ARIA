from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    domain = params.get("domain", "example.com")
    return {"domain": domain, "registrar": "Example", "status": "ok"}
