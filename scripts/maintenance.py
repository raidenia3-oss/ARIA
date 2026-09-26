"""ARIA OS — Automated Maintenance Procedures"""

import os
import shutil
import subprocess
import psutil
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MaintenanceManager:
    def __init__(self):
        self.log_file = Path('logs/maintenance.log')
        self.log_file.parent.mkdir(exist_ok=True)

    def log(self, message):
        """Log maintenance action"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(self.log_file, 'a') as f:
            f.write(log_entry + '\n')

    def cleanup_database(self):
        """Clean and optimize database"""
        self.log("▶ Database cleanup starting...")

        try:
            db_path = Path('AURA_APP/cerebro.db')
            if not db_path.exists():
                self.log("  ⚠️ cerebro.db not found, skipping vacuum")
                db_path = Path('AURA_APP/memory')
                if db_path.exists():
                    self.log(f"  ℹ️ Using JSON memory store at {db_path}")
                return

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cursor.execute("VACUUM")
            self.log("  ✅ Database vacuumed")

            cursor.execute("ANALYZE")
            self.log("  ✅ Database analyzed")

            size_before = db_path.stat().st_size / (1024 * 1024)
            self.log(f"  ✅ Database size: {size_before:.2f} MB")

            conn.close()
        except Exception as e:
            self.log(f"  ❌ Database cleanup failed: {e}")

    def rotate_old_records(self):
        """Archive old records (keep last 90 days)"""
        self.log("▶ Rotating old records...")

        try:
            db_path = Path('AURA_APP/cerebro.db')
            if not db_path.exists():
                self.log("  ⚠️ cerebro.db not found, skipping rotation")
                return

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()

            cursor.execute(
                "DELETE FROM conversations WHERE timestamp < ?",
                (cutoff_date,)
            )

            deleted = cursor.rowcount
            conn.commit()
            conn.close()

            self.log(f"  ✅ Deleted {deleted} old records")
        except Exception as e:
            self.log(f"  ❌ Record rotation failed: {e}")

    def cleanup_logs(self):
        """Clean old logs"""
        self.log("▶ Log cleanup starting...")

        try:
            logs_dir = Path('logs')
            cutoff = datetime.now() - timedelta(days=30)

            deleted_count = 0
            for log_file in logs_dir.glob('*.log'):
                if log_file.stat().st_mtime < cutoff.timestamp():
                    log_file.unlink()
                    deleted_count += 1

            self.log(f"  ✅ Deleted {deleted_count} old log files")
        except Exception as e:
            self.log(f"  ❌ Log cleanup failed: {e}")

    def rotate_logs(self):
        """Rotate logs if too large"""
        self.log("▶ Log rotation starting...")

        try:
            logs_dir = Path('logs')

            for log_file in logs_dir.glob('*.log'):
                size_mb = log_file.stat().st_size / (1024 * 1024)

                if size_mb > 100:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_name = f"{log_file.stem}_{timestamp}.log"
                    backup_path = log_file.parent / backup_name

                    log_file.rename(backup_path)
                    self.log(f"  ✅ Rotated {log_file.name}")
        except Exception as e:
            self.log(f"  ❌ Log rotation failed: {e}")

    def check_system_health(self):
        """Check system resource usage"""
        self.log("▶ System health check...")

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            self.log(f"  CPU: {cpu_percent}%")

            memory = psutil.virtual_memory()
            self.log(f"  Memory: {memory.percent}% ({memory.used / (1024**3):.2f} GB / {memory.total / (1024**3):.2f} GB)")

            disk = psutil.disk_usage('/')
            self.log(f"  Disk: {disk.percent}% ({disk.used / (1024**3):.2f} GB / {disk.total / (1024**3):.2f} GB)")

            if cpu_percent > 80:
                self.log("  ⚠️ HIGH CPU USAGE")
            if memory.percent > 80:
                self.log("  ⚠️ HIGH MEMORY USAGE")
            if disk.percent > 90:
                self.log("  ⚠️ LOW DISK SPACE")
        except Exception as e:
            self.log(f"  ❌ Health check failed: {e}")

    def clear_cache(self):
        """Clear application cache"""
        self.log("▶ Cache clearing...")

        try:
            cache_dirs = [
                Path('AURA_APP/.cache'),
                Path('AURA_APP/__pycache__'),
                Path('.pytest_cache'),
            ]

            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    self.log(f"  ✅ Cleared {cache_dir}")
        except Exception as e:
            self.log(f"  ❌ Cache clearing failed: {e}")

    def run_full_maintenance(self):
        """Run complete maintenance suite"""
        self.log("=" * 80)
        self.log("ARIA OS — Full Maintenance Cycle")
        self.log("=" * 80)

        self.check_system_health()
        self.cleanup_database()
        self.rotate_old_records()
        self.rotate_logs()
        self.cleanup_logs()
        self.clear_cache()

        self.log("=" * 80)
        self.log("✅ Maintenance complete")
        self.log("=" * 80)

if __name__ == '__main__':
    manager = MaintenanceManager()
    manager.run_full_maintenance()
