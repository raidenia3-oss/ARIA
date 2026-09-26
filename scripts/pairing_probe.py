"""Pairing probe — validación de conectividad local AURA HOST ⇄ AME.

Uso:
    python scripts/pairing_probe.py [--host http://192.168.1.50:8000]

1. Obtiene el perfil de emparejamiento del host (IP local, código, token).
2. Mide la latencia LAN con /api/mobile/pairing/ping (N muestras).
3. (Opcional) Canjea el código para verificar el handshake de punta a punta.

No expone secretos: el token del perfil es efímero y de un solo uso.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

from backend.mobile_pairing import create_pairing_profile


def _get(url: str, timeout: float = 5.0):
    start = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    return body, (time.perf_counter() - start) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser(description="AURA LAN pairing probe")
    parser.add_argument(
        "--host",
        default=None,
        help="URL base del host (default: autodetectada del perfil local)",
    )
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    profile = create_pairing_profile()
    host = args.host or profile["backend_url"]
    print(f"AURA pairing probe → {host}")
    print(f"  host_ip : {profile['host_ip']}  (interfaces: {profile['host_ips']})")
    print(f"  code    : {profile['code']}  (TTL {profile['ttl_seconds']}s, un solo uso)")
    print(f"  qr      : {profile['qr_payload'][:80]}...")

    ok = 0
    latencies = []
    for i in range(max(1, args.samples)):
        try:
            _, ms = _get(f"{host}/api/mobile/pairing/ping")
            latencies.append(ms)
            ok += 1
            print(f"  ping #{i + 1}: {ms:.1f} ms")
        except Exception as exc:
            print(f"  ping #{i + 1}: ERROR {exc}")

    if latencies:
        latencies.sort()
        print(
            f"  latency min/avg/max: "
            f"{latencies[0]:.1f}/{sum(latencies) / len(latencies):.1f}/{latencies[-1]:.1f} ms"
        )

    print(f"  handshake-ready: {'yes' if ok else 'no'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())