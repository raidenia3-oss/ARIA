#!/usr/bin/env python3
"""AURA OS — Package setup for production release.

The version is never written here: it is read from the single source of truth in
``pyproject.toml`` via ``aria_version.ARIA_VERSION`` (which
``tools/sync_version.py`` keeps in sync with ``[project].version``).
"""

from setuptools import find_packages, setup

import aria_version

setup(
    name="aura-os",
    version=aria_version.ARIA_VERSION,
    description="Production-ready AI Operating System with 300+ providers, mobile support, and netrunner mode",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="AURA Team",
    url="https://github.com/your-org/aura-os",
    packages=find_packages(where="."),
    include_package_data=True,
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.141.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.13.5",
        "sqlalchemy>=2.0.23",
        "aiohttp>=3.9.1",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "websockets>=12.0",
        "PyJWT>=2.8.0",
        "bcrypt>=4.1.0",
        "httpx>=0.28.1",
        "flet>=0.24.0",
    ],
    extras_require={
        "mobile": ["flet>=0.24.0"],
        "desktop": ["PyQt5>=5.15.0"],
    },
    entry_points={
        "console_scripts": [
            "aura-server=uvicorn:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
