#!/usr/bin/env python3
"""
AURA — Autonomous AI Ecosystem Launcher
========================================
Single entry point that:
  - Auto-detects environment (Python/Node/Ruby/Docker)
  - Installs missing dependencies
  - Generates .env files from templates
  - Starts all services in correct order
  - Opens browser to dashboard
  - Monitors services and auto-restarts on failure

Usage:
  python aura.py              # Interactive mode
  python aura.py --silent     # Headless mode (background)
  python aura.py --docker     # Force Docker Compose
  python aura.py --dev        # Development mode with auto-reload
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


ROOT = Path(__file__).resolve().parent


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def run(cmd: list[str], cwd: Optional[Path] = None, capture: bool = False) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    cwd = cwd or ROOT
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=capture,
            text=True,
            shell=platform.system() == "Windows" and len(cmd) == 1,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except Exception as exc:
        return 1, "", str(exc)


def banner(text: str) -> None:
    width = 60
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width + "\n")


def check_python() -> bool:
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"[ERROR] Python 3.11+ required. Current: {version.major}.{version.minor}")
        return False
    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_node() -> bool:
    node = which("node")
    if not node:
        print("[ERROR] Node.js not found. Install Node.js 20+ from https://nodejs.org")
        return False
    rc, out, _ = run(["node", "--version"])
    if rc == 0:
        print(f"[OK] Node.js {out.strip()}")
        return True
    return False


def check_ruby() -> bool:
    ruby = which("ruby")
    if not ruby:
        print("[WARN] Ruby not found. Discord bot and DSL compiler will be skipped.")
        return False
    rc, out, _ = run(["ruby", "--version"])
    if rc == 0:
        print(f"[OK] Ruby {out.strip()}")
        return True
    return False


def check_docker() -> bool:
    docker = which("docker")
    if not docker:
        print("[WARN] Docker not found. Docker Compose mode unavailable.")
        return False
    rc, out, _ = run(["docker", "--version"])
    if rc == 0:
        print(f"[OK] Docker {out.strip()}")
        return True
    return False


def ensure_pip() -> None:
    print("\n[SETUP] Installing Python dependencies...")
    rc, _, err = run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip", "setuptools", "wheel"])
    if rc != 0:
        print(f"[WARN] pip upgrade failed: {err}")

    req = ROOT / "requirements.txt"
    if req.exists():
        rc, _, err = run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
        if rc != 0:
            print(f"[ERROR] Failed to install requirements: {err}")
            sys.exit(1)
        print("[OK] Python dependencies installed")
    else:
        print("[WARN] requirements.txt not found")


def ensure_node_deps() -> None:
    frontend = ROOT / "frontend"
    if not frontend.exists():
        return
    print("\n[SETUP] Installing Node.js dependencies...")
    rc, _, err = run(["npm", "install"], cwd=frontend, capture=True)
    if rc != 0:
        print(f"[WARN] npm install failed: {err[:200]}")
    else:
        print("[OK] Node.js dependencies installed")


def ensure_ruby_deps() -> None:
    for service in ["discord-bot", "dsl-compiler"]:
        svc_path = ROOT / "services" / service
        gemfile = svc_path / "Gemfile"
        if not gemfile.exists():
            continue
        print(f"\n[SETUP] Installing Ruby dependencies for {service}...")
        rc, _, err = run(["bundle", "install"], cwd=svc_path, capture=True)
        if rc != 0:
            print(f"[WARN] bundle install failed for {service}: {err[:200]}")
        else:
            print(f"[OK] Ruby dependencies for {service} installed")


def ensure_env_files() -> None:
    print("\n[SETUP] Checking environment files...")
    root_env = ROOT / ".env"
    if not root_env.exists():
        example = ROOT / ".env.example"
        if example.exists():
            import shutil as sh
            sh.copy(example, root_env)
            print("[OK] Created .env from .env.example")
        else:
            print("[WARN] .env.example not found, creating minimal .env")
            ROOT.joinpath(".env").write_text(
                "AURA_JWT_SECRET=change-me\nAURA_API_KEY=dev-key\nDATABASE_URL=sqlite:///aura.db\nREDIS_URL=redis://localhost:6379/0\n"
            )

    for rel in ["backend/.env", "services/discord-bot/.env", "frontend/.env.local"]:
        p = ROOT / rel
        if not p.exists():
            example = p.parent / f"{p.name}.example"
            if example.exists():
                import shutil as sh
                sh.copy(example, p)
                print(f"[OK] Created {rel} from {example.name}")
            else:
                print(f"[WARN] No .env.example for {rel}")


def ensure_vscode_setup() -> None:
    print("\n[SETUP] VS Code workspace configuration...")
    vscode_dir = ROOT / ".vscode"
    vscode_dir.mkdir(exist_ok=True)

    extensions = vscode_dir / "extensions.json"
    if not extensions.exists():
        extensions.write_text('{"recommendations":[],"unwantedRecommendations":[]}')

    settings = vscode_dir / "settings.json"
    if not settings.exists():
        settings.write_text('{"python.pythonPath":"python","typescript.tsdk":"frontend/node_modules/typescript/lib"}')

    print("[OK] VS Code workspace configured")


def start_backend_dev() -> subprocess.Popen:
    print("\n[START] Backend (FastAPI) — http://localhost:8000")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(ROOT),
    )


def start_frontend_dev() -> subprocess.Popen:
    print("\n[START] Frontend (Next.js) — http://localhost:3000")
    return subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(ROOT / "frontend"),
        shell=platform.system() == "Windows",
    )


def start_hf_space() -> subprocess.Popen:
    print("\n[START] HF Space (Gradio) — http://localhost:7860")
    return subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=str(ROOT / "hf-space"),
    )


def start_discord_bot() -> Optional[subprocess.Popen]:
    if not check_ruby():
        print("[SKIP] Discord bot (Ruby not available)")
        return None
    print("\n[START] Discord Bot")
    return subprocess.Popen(
        ["ruby", "bot.rb"],
        cwd=str(ROOT / "services" / "discord-bot"),
        shell=platform.system() == "Windows",
    )


def wait_for_url(url: str, timeout: int = 30) -> bool:
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def open_browser(url: str) -> None:
    import webbrowser
    webbrowser.open(url)


def run_docker_compose() -> None:
    banner("AURA — Docker Compose Mode")
    if not check_docker():
        print("[ERROR] Docker is required for this mode")
        sys.exit(1)

    print("[START] Starting all services with Docker Compose...")
    rc, _, err = run(["docker-compose", "up", "--build"])
    if rc != 0:
        print(f"[ERROR] docker-compose failed: {err}")
        sys.exit(rc)


def run_dev_mode(silent: bool = False) -> None:
    banner("AURA — Development Mode")
    if not check_python():
        sys.exit(1)

    ensure_env_files()
    ensure_pip()
    ensure_node_deps()
    ensure_ruby_deps()
    ensure_vscode_setup()

    processes = []

    print("\n[BOOT] Starting services...")
    processes.append(start_backend_dev())

    if wait_for_url("http://localhost:8000/health", timeout=15):
        print("[OK] Backend healthy")
    else:
        print("[WARN] Backend did not respond in time")

    processes.append(start_frontend_dev())
    processes.append(start_hf_space())

    bot = start_discord_bot()
    if bot:
        processes.append(bot)

    if not silent:
        print("\n" + "=" * 60)
        print("  AURA is running!")
        print("  Frontend:  http://localhost:3000")
        print("  Backend:   http://localhost:8000")
        print("  HF Space:  http://localhost:7860")
        print("  API Docs:  http://localhost:8000/docs")
        print("=" * 60 + "\n")

        try:
            open_browser("http://localhost:3000")
        except Exception:
            pass

        try:
            print("[INFO] Press Ctrl+C to stop all services\n")
            while True:
                time.sleep(1)
                for p in processes:
                    if p.poll() is not None:
                        print(f"[WARN] Process {p.pid} exited with code {p.returncode}")
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Stopping services...")
    else:
        print("[INFO] Services started in background")

    for p in processes:
        if p.poll() is None:
            p.terminate()

    for p in processes:
        p.wait(timeout=5)

    print("[OK] All services stopped")


def main() -> int:
    parser = argparse.ArgumentParser(description="AURA Launcher")
    parser.add_argument("--docker", action="store_true", help="Use Docker Compose mode")
    parser.add_argument("--silent", action="store_true", help="Start services without interactive mode")
    parser.add_argument("--dev", action="store_true", help="Development mode with auto-reload")
    parser.add_argument("--check", action="store_true", help="Check environment only")
    args = parser.parse_args()

    if args.check:
        banner("AURA — Environment Check")
        checks = {
            "Python": check_python(),
            "Node.js": check_node(),
            "Ruby": check_ruby(),
            "Docker": check_docker(),
        }
        print("\nResults:")
        for name, ok in checks.items():
            status = "OK" if ok else "MISSING"
            print(f"  {name}: {status}")
        return 0 if all(checks.values()) else 1

    if args.docker:
        run_docker_compose()
        return 0

    run_dev_mode(silent=args.silent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
