#!/usr/bin/env python3
"""Deploy script for AURA backend on Railway/Render."""
import os
import sys
import subprocess


def check_env():
    required = ["AURA_API_KEY", "PORT", "AURA_JWT_SECRET"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        sys.exit(1)


def install_deps():
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", "backend/requirements.txt"], check=True)


def init_db():
    from backend.database import engine
    from backend.models import Base
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")


def run_migrations():
    import subprocess
    subprocess.run(["alembic", "upgrade", "head"], cwd="backend", check=False)
    print("Migrations applied.")


def run():
    check_env()
    install_deps()
    init_db()
    run_migrations()
    subprocess.run([sys.executable, "backend/main.py"], check=True)


if __name__ == "__main__":
    run()
