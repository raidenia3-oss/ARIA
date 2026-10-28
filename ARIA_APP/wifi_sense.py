"""WiFi sensing utilities for ARIA (stdlib only, read-only)."""
import re
import subprocess


def _run(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=15)
    except Exception:
        return ""


def scan_networks():
    out = _run(["netsh", "wlan", "show", "networks", "mode=bssid"])
    nets = []
    cur = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("SSID"):
            if cur:
                nets.append(cur)
            name = line.split(":", 1)[-1].strip() if ":" in line else ""
            cur = {"ssid": name, "bssids": []}
        elif cur is not None and line.startswith("BSSID"):
            cur["bssids"].append({"bssid": line.split(":", 1)[-1].strip()})
        elif cur is not None and cur["bssids"]:
            last = cur["bssids"][-1]
            low = line.lower()
            if low.startswith("signal"):
                m = re.search(r"(\d+)", line)
                if m:
                    last["signal_pct"] = int(m.group(1))
            elif low.startswith("channel"):
                m = re.search(r"(\d+)", line)
                if m:
                    last["channel"] = int(m.group(1))
            elif low.startswith("radio type"):
                last["radio"] = line.split(":", 1)[-1].strip()
            elif low.startswith("band"):
                last["band"] = line.split(":", 1)[-1].strip()
    if cur:
        nets.append(cur)
    return nets


def summary():
    nets = scan_networks()
    channels = {}
    bands = {}
    for n in nets:
        for b in n.get("bssids", []):
            ch = b.get("channel")
            if ch is not None:
                channels[ch] = channels.get(ch, 0) + 1
            band = b.get("band")
            if band:
                bands[band] = bands.get(band, 0) + 1
    # congestion: channels with >2 networks
    congested = [ch for ch, c in channels.items() if c >= 3]
    return {
        "network_count": len(nets),
        "bssid_count": sum(len(n.get("bssids", [])) for n in nets),
        "channels": channels,
        "bands": bands,
        "congested_channels": congested,
    }
