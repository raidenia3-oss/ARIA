#!/usr/bin/env python3
"""
AURA Idle Detector — Detecta cuando la PC no está siendo usada para entrenar en la nube.

Estrategia:
  - CPU usage < 15% durante X minutos
  - No input de mouse/teclado durante X minutos
  - No procesos activos de entrenamiento local
  - La PC está conectada a corriente (opcional, para laptops)

Uso:
  python scripts/idle_detector.py --check
  python scripts/idle_detector.py --monitor --interval 60 --threshold 300
  python scripts/idle_detector.py --status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed. CPU detection may be limited.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IdleDetector")

REPO_ROOT = Path(__file__).resolve().parent.parent
IDLE_STATE_FILE = REPO_ROOT / "idle_state.json"

DEFAULT_CPU_THRESHOLD = 15.0
DEFAULT_INPUT_THRESHOLD = 300
DEFAULT_CHECK_INTERVAL = 60


class IdleDetector:
    """Detecta inactividad del sistema."""

    def __init__(self, cpu_threshold: float = DEFAULT_CPU_THRESHOLD, input_threshold: int = DEFAULT_INPUT_THRESHOLD):
        self.cpu_threshold = cpu_threshold
        self.input_threshold = input_threshold
        self.last_input_seconds = self._get_idle_time()

    def _get_idle_time(self) -> int:
        system = platform.system()
        try:
            if system == "Windows":
                import ctypes
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
                info = LASTINPUTINFO()
                info.cbSize = ctypes.sizeof(LASTINPUTINFO)
                ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
                millis = int(time.time() * 1000) - info.dwTime
                return millis // 1000
            elif system == "Darwin":
                import subprocess
                result = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if "HIDIdleTime" in line:
                        ns = int(line.split("=")[1].strip())
                        return ns // 1_000_000_000
            elif system == "Linux":
                import subprocess
                result = subprocess.run(["xprintidle"], capture_output=True, text=True)
                return int(result.stdout.strip()) // 1000
        except Exception:
            pass
        return 0

    def _get_cpu_usage(self) -> float:
        try:
            if HAS_PSUTIL:
                return float(psutil.cpu_percent(interval=1))
        except Exception:
            pass
        return 0.0

    def is_idle(self, cpu_threshold: Optional[float] = None, input_threshold: Optional[int] = None) -> Dict[str, Any]:
        cpu_limit = cpu_threshold or self.cpu_threshold
        input_limit = input_threshold or self.input_threshold
        idle_seconds = self._get_idle_time()
        cpu_usage = self._get_cpu_usage()
        input_idle = idle_seconds >= input_limit
        cpu_idle = cpu_usage < cpu_limit
        is_idle = input_idle and cpu_idle
        result = {
            "is_idle": is_idle,
            "idle_seconds": idle_seconds,
            "input_idle": input_idle,
            "cpu_usage_percent": cpu_usage,
            "cpu_idle": cpu_idle,
            "thresholds": {"cpu": cpu_limit, "input_seconds": input_limit},
            "timestamp": datetime.now().isoformat(),
        }
        return result

    def monitor(self, interval: int = DEFAULT_CHECK_INTERVAL, threshold: int = DEFAULT_INPUT_THRESHOLD, max_checks: int = 60) -> Dict[str, Any]:
        logger.info(f"Monitoring idle state every {interval}s (input threshold: {threshold}s)")
        idle_count = 0
        checks = 0
        for i in range(max_checks):
            result = self.is_idle(input_threshold=threshold)
            checks += 1
            status = "IDLE" if result["is_idle"] else "ACTIVE"
            logger.info(f"Check {i+1}: {status} (input={result['idle_seconds']}s, cpu={result['cpu_usage_percent']:.1f}%)")
            if result["is_idle"]:
                idle_count += 1
            else:
                idle_count = 0
            time.sleep(interval)
        return {
            "checks": checks,
            "idle_checks": idle_count,
            "consecutive_idle": idle_count,
            "is_currently_idle": self.is_idle(input_threshold=threshold)["is_idle"],
        }


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Idle Detector")
    p.add_argument("--check", action="store_true", help="Check idle state once")
    p.add_argument("--monitor", action="store_true", help="Monitor idle state continuously")
    p.add_argument("--interval", type=int, default=DEFAULT_CHECK_INTERVAL, help="Check interval in seconds")
    p.add_argument("--threshold", type=int, default=DEFAULT_INPUT_THRESHOLD, help="Input idle threshold in seconds")
    p.add_argument("--cpu-threshold", type=float, default=DEFAULT_CPU_THRESHOLD, help="CPU usage threshold")
    p.add_argument("--status", action="store_true", help="Show status")
    args = p.parse_args()

    detector = IdleDetector(cpu_threshold=args.cpu_threshold, input_threshold=args.threshold)

    if args.status:
        result = detector.is_idle()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.monitor:
        result = detector.monitor(interval=args.interval, threshold=args.threshold)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    result = detector.is_idle()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
