"""Maintenance — Mantenimiento del sistema"""

import json
import shutil
from pathlib import Path
from datetime import datetime


class MaintenanceManager:
    """Mantenimiento del sistema"""

    def __init__(self):
        self.data_dir = Path('ARIA_v4/AURA_APP/data')
        self.log_dir = Path('ARIA_v4/AURA_APP/logs')

    def clear_cache(self) -> int:
        count = 0
        for f in self.data_dir.rglob('*'):
            if f.is_file() and f.suffix in ['.json', '.cache', '.tmp']:
                f.unlink()
                count += 1
        return count

    def clear_old_logs(self, days: int = 30) -> int:
        count = 0
        cutoff = datetime.now().timestamp() - (days * 86400)
        for f in self.log_dir.rglob('*.log'):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                count += 1
        return count

    def cleanup_temp(self) -> int:
        count = 0
        for f in self.data_dir.rglob('*.tmp'):
            f.unlink()
            count += 1
        return count

    def log(self, message: str) -> None:
        log_file = self.log_dir / 'maintenance.log'
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()} — {message}\n")


if __name__ == '__main__':
    m = MaintenanceManager()
    print(f"Cache cleared: {m.clear_cache()} files")
    print(f"Logs cleared: {m.clear_old_logs()} files")
