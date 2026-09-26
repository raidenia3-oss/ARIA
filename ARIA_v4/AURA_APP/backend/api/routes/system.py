"""System Route"""

from typing import Dict


async def health_route() -> Dict:
    return {
        'status': 'healthy',
        'version': '4.0.0',
        'timestamp': '2026-09-20T18:43:23-05:00',
    }


async def status_route() -> Dict:
    return {
        'backend': 'running',
        'mode': 'aria-v4',
        'version': '4.0.0',
    }
