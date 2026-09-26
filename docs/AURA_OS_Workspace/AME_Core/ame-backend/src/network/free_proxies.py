#!/usr/bin/env python3
"""
free_proxies.py — Cazador de proxies públicos gratuitos.
Extrae proxies de fuentes públicas y los valida contra api.ipify.org.
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

import requests
import urllib3
from requests.exceptions import RequestException

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class FreeProxyHunter:
    def __init__(self, concurrency: int = 15, validation_timeout: int = 5, max_candidates: int = 120) -> None:
        self.concurrency = concurrency
        self.validation_timeout = validation_timeout
        self.max_candidates = max_candidates
        self.pool: List[dict] = []
        self.lock = threading.Lock()
        self._stop = False

    def _fetch_proxies_from_sources(self) -> List[str]:
        proxies: List[str] = []

        try:
            url = "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all&simplified=true"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                candidates = [line.strip() for line in r.text.splitlines() if line.strip()]
                proxies.extend(candidates)
        except RequestException as e:
            logger.warning(f"[Hunter] proxyscrape fallo: {e}")

        try:
            url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                candidates = [line.strip() for line in r.text.splitlines() if line.strip()]
                proxies.extend(candidates)
        except RequestException as e:
            logger.warning(f"[Hunter] github raw fallo: {e}")

        seen = set()
        unique = []
        for p in proxies:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return unique[: self.max_candidates]

    def validate_proxy(self, ip_port: str) -> bool:
        if self._stop:
            return False
        proxies = {"http": f"http://{ip_port}", "https": f"http://{ip_port}"}
        try:
            r = requests.get("https://api.ipify.org", proxies=proxies, timeout=self.validation_timeout, verify=False)
            if r.status_code == 200 and r.text.strip():
                logger.debug(f"[Hunter] Proxy valido: {ip_port} -> {r.text.strip()}")
                return True
        except RequestException:
            pass
        return False

    def harvest(self, target: int = 3) -> List[dict]:
        """Extrae y valida proxies hasta alcanzar el target.
        Devuelve hasta `target` proxies validos como maximo.
        """
        logger.info(f"[Hunter] Iniciando caza de {target} proxies validos...")
        self.pool = []
        self._stop = False

        candidates = self._fetch_proxies_from_sources()
        random.shuffle(candidates)
        candidates = candidates[: self.max_candidates]
        logger.info(f"[Hunter] Candidatos a validar: {len(candidates)}")

        count = 0
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {executor.submit(self.validate_proxy, c): c for c in candidates}
            for future in as_completed(futures):
                if self._stop:
                    break
                if future.result():
                    with self.lock:
                        self.pool.append({
                            "server": futures[future],
                            "username": None,
                            "password": None,
                        })
                    count += 1
                    if count >= target:
                        self._stop = True
                        break

        logger.info(f"[Hunter] Pool final: {len(self.pool)} proxies validos")
        return self.pool[:target]

    def get_random_proxy(self) -> Optional[dict]:
        with self.lock:
            if not self.pool:
                return None
            return random.choice(self.pool)

    def stop(self) -> None:
        self._stop = True


hunter = FreeProxyHunter()
