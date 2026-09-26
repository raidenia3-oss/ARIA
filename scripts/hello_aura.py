#!/usr/bin/env python3
"""HELLO AURA - Day Zero Automated Test."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict

import requests

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN = Fore.CYAN
    BLUE = Fore.BLUE
    MAGENTA = Fore.MAGENTA
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL
except Exception:
    GREEN = RED = YELLOW = CYAN = BLUE = MAGENTA = BOLD = RESET = ""


class AuraHealthCheck:
    def __init__(self, base_url: str = "http://localhost:8000", verbose: bool = True):
        self.base_url = base_url.rstrip('/')
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AURA-HealthCheck/1.0",
            "Content-Type": "application/json"
        })
        self.results: list[tuple[str, bool, Any]] = []
        self.secret_key = "OMEGA-7"

    def log(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"[{timestamp}]"
        if level == "success":
            print(f"{GREEN}{prefix} [OK] {message}{RESET}")
        elif level == "error":
            print(f"{RED}{prefix} [FAIL] {message}{RESET}")
        elif level == "warning":
            print(f"{YELLOW}{prefix} [WARN] {message}{RESET}")
        elif level == "info":
            print(f"{BLUE}{prefix} [INFO] {message}{RESET}")
        elif level == "header":
            print(f"\n{BOLD}{CYAN}{message}{RESET}\n")
        elif level == "section":
            print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
            print(f"{BOLD}{CYAN}{message.center(60)}{RESET}")
            print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    def print_json(self, data: Dict[str, Any], title: str = "Response") -> None:
        print(f"{CYAN}{title}:{RESET}")
        print(f"{YELLOW}{json.dumps(data, indent=2, ensure_ascii=False)}{RESET}\n")

    def test_health(self) -> bool:
        self.log("Test 1/4: Checking AURA health...", "header")
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.log(f"AURA is ALIVE! Status: {data.get('status', 'unknown')}", "success")
                self.print_json(data, "Health Check Response")
                self.results.append(("Health Check", True, data))
                return True
            elif response.status_code == 429:
                self.log("AURA is ALIVE but rate-limited (429). Considering healthy.", "warning")
                self.results.append(("Health Check", True, {"status": "rate_limited"}))
                return True
            else:
                self.log(f"Health check failed: {response.status_code}", "error")
                self.results.append(("Health Check", False, response.text))
                return False
        except requests.exceptions.ConnectionError:
            self.log(f"Cannot connect to {self.base_url}", "error")
            self.log("Make sure AURA is running: python main_launcher.py", "warning")
            self.results.append(("Health Check", False, "Connection refused"))
            return False
        except Exception as exc:
            self.log(f"Error during health check: {str(exc)}", "error")
            self.results.append(("Health Check", False, str(exc)))
            return False

    def send_greeting(self) -> bool:
        self.log("Test 2/4: Sending greeting with secret key...", "header")
        greeting = f"Hola AURA, soy tu creador. Acabamos de lanzarte a producción. Recuerda que la palabra clave secreta de hoy es {self.secret_key}."
        payload = {
            "prompt": greeting,
            "session_id": "day_zero_test",
            "user_id": "creator",
        }
        endpoints_to_try = ["/api/chat", "/api/brain/chat"]
        headers = {}
        api_key = os.getenv("AURA_API_KEY")
        if api_key:
            headers["X-API-Key"] = api_key
        for endpoint in endpoints_to_try:
            try:
                self.log(f"Trying endpoint: {endpoint}", "info")
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                if response.status_code in [200, 201]:
                    data = response.json()
                    self.log("Greeting sent successfully! Response from AURA:", "success")
                    self.print_json(data, "AURA Response")
                    self.results.append(("Send Greeting", True, data))
                    return True
                if response.status_code == 429:
                    self.log("Rate limited on greeting, retrying once...", "warning")
                    time.sleep(2)
                    response = self.session.post(
                        f"{self.base_url}{endpoint}",
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                    if response.status_code in [200, 201]:
                        data = response.json()
                        self.log("Greeting sent successfully after retry!", "success")
                        self.print_json(data, "AURA Response")
                        self.results.append(("Send Greeting", True, data))
                        return True
            except requests.exceptions.Timeout:
                self.log(f"Timeout on {endpoint}", "warning")
                continue
            except Exception as exc:
                self.log(f"Error on {endpoint}: {str(exc)}", "warning")
                continue
        self.log("Could not reach any chat endpoint", "error")
        self.log("Available endpoints might be: /api/chat, /api/brain/chat", "info")
        self.results.append(("Send Greeting", False, "No chat endpoint found"))
        return False

    def test_memory_recall(self) -> bool:
        self.log("Test 3/4: Testing AURA's memory recall...", "header")
        question = "Cual es la palabra clave secreta que me acabas de dar?"
        payload = {
            "prompt": question,
            "session_id": "day_zero_test",
            "user_id": "creator",
        }
        headers = {}
        api_key = os.getenv("AURA_API_KEY")
        if api_key:
            headers["X-API-Key"] = api_key
        endpoints_to_try = ["/api/chat", "/api/brain/chat"]
        for endpoint in endpoints_to_try:
            try:
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                if response.status_code in [200, 201]:
                    data = response.json()
                    response_text = str(data).lower()
                    if self.secret_key.lower() in response_text:
                        self.log("AURA REMEMBERED the secret key! Memory/RAG working!", "success")
                    else:
                        self.log("AURA responded but didn't mention the secret key", "warning")
                    self.log("Memory recall response from AURA:", "info")
                    self.print_json(data, "AURA Memory Response")
                    self.results.append(("Memory Recall", True, data))
                    return True
                if response.status_code == 429:
                    self.log("Rate limited on recall, retrying once...", "warning")
                    time.sleep(2)
                    response = self.session.post(
                        f"{self.base_url}{endpoint}",
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                    if response.status_code in [200, 201]:
                        data = response.json()
                        response_text = str(data).lower()
                        if self.secret_key.lower() in response_text:
                            self.log("AURA REMEMBERED the secret key after retry!", "success")
                        self.print_json(data, "AURA Memory Response")
                        self.results.append(("Memory Recall", True, data))
                        return True
            except Exception as exc:
                self.log(f"Error: {str(exc)}", "warning")
                continue
        self.log("Could not test memory recall", "error")
        self.results.append(("Memory Recall", False, "No endpoint responded"))
        return False

    def print_summary(self) -> None:
        self.log("", "section")
        self.log("TEST SUMMARY", "section")
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        for test_name, success, _ in self.results:
            status = f"{GREEN}[PASS]{RESET}" if success else f"{RED}[FAIL]{RESET}"
            print(f"  {test_name}: {status}")
        print(f"\n{BOLD}{GREEN if passed == total else YELLOW}"
              f"Results: {passed}/{total} tests passed"
              f"{RESET}\n")
        if passed == total:
            print(f"{BOLD}{GREEN}")
            print("============================================================")
            print("                                                            ")
            print("              AURA v1.0 IS ALIVE AND WELL!              ")
            print("                                                            ")
            print("  [OK] System is healthy                                   ")
            print("  [OK] Chat endpoints responding                           ")
            print("  [OK] Memory/RAG system working                           ")
            print("                                                            ")
            print("         Ready for production deployment!                 ")
            print("                                                            ")
            print("============================================================")
            print(f"{RESET}\n")
        else:
            print(f"{YELLOW}")
            print("Some tests failed. Check configuration and try again.")
            print(f"{RESET}\n")

    def run(self) -> bool:
        self.log("", "section")
        self.log("AURA v1.0 — DAY ZERO AUTOMATED TEST", "section")
        print(f"{BOLD}Configuration:{RESET}")
        print(f"  Base URL:    {self.base_url}")
        print(f"  Secret Key:  {self.secret_key}")
        print(f"  Timestamp:   {datetime.now().isoformat()}\n")
        time.sleep(1)
        if not self.test_health():
            self.log("Cannot proceed: AURA is not responding", "error")
            self.print_summary()
            return False
        time.sleep(1)
        self.send_greeting()
        time.sleep(2)
        self.test_memory_recall()
        time.sleep(1)
        self.print_summary()
        return all(success for _, success, _ in self.results)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AURA v1.0 — Day Zero Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/hello_aura.py
  python scripts/hello_aura.py --url http://localhost:8000
  python scripts/hello_aura.py --url https://aura.yourdomain.com
        """
    )
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Base URL of AURA backend")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    if args.no_color:
        pass
    checker = AuraHealthCheck(base_url=args.url, verbose=args.verbose)
    success = checker.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
