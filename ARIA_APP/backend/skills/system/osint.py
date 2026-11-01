import socket
import urllib.request
from typing import Any, Dict

WHOIS_SERVERS = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "io": "whois.nic.io",
}


def _whois(target: str) -> str:
    tld = target.rsplit(".", 1)[-1].lower()
    server = WHOIS_SERVERS.get(tld, "whois.iana.org")
    try:
        with socket.create_connection((server, 43), timeout=10) as s:
            s.sendall((target + "\r\n").encode())
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
        return data.decode("utf-8", errors="ignore")[:3000]
    except Exception as e:
        return f"whois error: {e}"

def run(params: Dict[str, Any]) -> Dict[str, Any]:
    target = str(params.get("target", "")).strip()
    if not target:
        return {"status": "error", "error": "target requerido"}
    result: Dict[str, Any] = {"status": "ok", "target": target}
    try:
        result["ip"] = socket.gethostbyname(target)
    except Exception as e:
        result["ip_error"] = str(e)
    try:
        result["reverse_dns"] = socket.gethostbyaddr(result.get("ip", target))[0]
    except Exception as e:
        result["reverse_dns_error"] = str(e)
    try:
        req = urllib.request.Request("https://" + target, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            result["http_status"] = r.status
            result["headers"] = dict(r.headers)
    except Exception as e:
        result["http_error"] = str(e)
    result["whois"] = _whois(target)
    return result
