"""
Shadow-Core Scheduler — Task Queue ligera sobre SQLite
Proporciona colas de tareas (Pub/Sub), cron jobs internos
y ejecucion programada sin dependencias pesadas (Redis no requerido).
"""
import sqlite3
import json
import time
import threading
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Callable, Any

# ── Configuracion ──
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AURA_Core', 'aura_tasks.db')
POLL_INTERVAL = 2  # segundos entre polling de tareas

logging.basicConfig(level=logging.INFO, format='%(asctime)s [Scheduler] %(levelname)s %(message)s')
logger = logging.getLogger('scheduler')


def init_db():
    """Crea las tablas de tareas si no existen."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'CREATE TABLE IF NOT EXISTS tasks ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        'channel TEXT NOT NULL,'
        'payload TEXT NOT NULL,'
        'status TEXT DEFAULT "pending",'
        'priority INTEGER DEFAULT 0,'
        'created_at TEXT DEFAULT CURRENT_TIMESTAMP,'
        'scheduled_at TEXT,'
        'started_at TEXT,'
        'completed_at TEXT,'
        'result TEXT,'
        'error TEXT)'
    )
    c.execute(
        'CREATE TABLE IF NOT EXISTS scheduled_jobs ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        'name TEXT UNIQUE NOT NULL,'
        'interval_seconds INTEGER NOT NULL,'
        'module_path TEXT NOT NULL,'
        'function_name TEXT NOT NULL,'
        'enabled INTEGER DEFAULT 1,'
        'last_run TEXT,'
        'next_run TEXT)'
    )
    c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_channel ON tasks(channel)')
    conn.commit()
    conn.close()
    logger.info("Base de datos inicializada: %s", DB_PATH)


# ── API de Cola de Tareas (Task Queue) ──
def publish(channel: str, payload: dict, priority: int = 0, delay_seconds: int = 0) -> int:
    """Publica un mensaje en un canal."""
    scheduled_at = (datetime.now() + timedelta(seconds=delay_seconds)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO tasks (channel, payload, priority, scheduled_at) VALUES (?, ?, ?, ?)',
        (channel, json.dumps(payload), priority, scheduled_at)
    )
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    logger.info("Tarea #%d publicada en canal %s (prioridad %d)", task_id, channel, priority)
    return task_id


def subscribe(channel: str, timeout: Optional[float] = None) -> Optional[dict]:
    """Espera y consume el siguiente mensaje de un canal."""
    start = time.time()
    while True:
        if timeout and (time.time() - start) > timeout:
            return None

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute(
            'SELECT id, channel, payload FROM tasks '
            'WHERE channel = ? AND status = "pending" AND scheduled_at <= ? '
            'ORDER BY priority DESC, id ASC LIMIT 1',
            (channel, now)
        )
        row = c.fetchone()

        if row:
            c.execute(
                'UPDATE tasks SET status = "processing", started_at = ? WHERE id = ?',
                (datetime.now().isoformat(), row[0])
            )
            conn.commit()
            conn.close()
            return {'id': row[0], 'channel': row[1], 'payload': json.loads(row[2])}

        conn.close()
        time.sleep(POLL_INTERVAL)


def acknowledge(task_id: int, result: Any = None, error: Optional[str] = None):
    """Marca una tarea como completada."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    status = 'failed' if error else 'completed'
    c.execute(
        'UPDATE tasks SET status = ?, completed_at = ?, result = ?, error = ? WHERE id = ?',
        (status, datetime.now().isoformat(), json.dumps(result) if result else None, error, task_id)
    )
    conn.commit()
    conn.close()
    if error:
        logger.error("Tarea #%d fallo: %s", task_id, error)
    else:
        logger.info("Tarea #%d completada", task_id)


def get_pending_count(channel: Optional[str] = None) -> int:
    """Cuenta tareas pendientes."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if channel:
        c.execute('SELECT COUNT(*) FROM tasks WHERE channel = ? AND status = "pending"', (channel,))
    else:
        c.execute('SELECT COUNT(*) FROM tasks WHERE status = "pending"')
    count = c.fetchone()[0]
    conn.close()
    return count


# ── Sistema de Cron Jobs ──
class CronJob:
    """Representa un trabajo programado."""
    def __init__(self, name: str, interval_seconds: int, callback: Callable, enabled: bool = True):
        self.name = name
        self.interval = interval_seconds
        self.callback = callback
        self.enabled = enabled
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        """Inicia el cron job en un hilo daemon."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='cron-' + self.name)
        self._thread.start()
        logger.info("Cron '%s' iniciado (cada %ds)", self.name, self.interval)

    def stop(self):
        """Detiene el cron job."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Cron '%s' detenido", self.name)

    def _run_loop(self):
        while not self._stop.is_set():
            if self.enabled:
                try:
                    self.last_run = datetime.now()
                    self.next_run = self.last_run + timedelta(seconds=self.interval)
                    self.callback()
                except Exception as e:
                    logger.error("Error en cron '%s': %s", self.name, e)
            self._stop.wait(self.interval)


class Scheduler:
    """Manejador de tareas programadas y colas."""
    def __init__(self):
        init_db()
        self.cron_jobs: dict = {}
        self._running = False

    def register_cron(self, name: str, interval_seconds: int, callback: Callable):
        """Registra un nuevo cron job."""
        job = CronJob(name, interval_seconds, callback)
        self.cron_jobs[name] = job
        logger.info("Cron '%s' registrado (cada %ds)", name, interval_seconds)
        return job

    def start_all(self):
        """Inicia todos los cron jobs."""
        for job in self.cron_jobs.values():
            job.start()
        self._running = True
        logger.info("Scheduler iniciado con %d cron jobs", len(self.cron_jobs))

    def stop_all(self):
        """Detiene todos los cron jobs."""
        for job in self.cron_jobs.values():
            job.stop()
        self._running = False
        logger.info("Scheduler detenido")

    def get_status(self) -> dict:
        """Retorna estado del scheduler."""
        status = {
            'running': self._running,
            'cron_jobs': {},
            'pending_tasks': get_pending_count(),
            'db_path': DB_PATH
        }
        for name, job in self.cron_jobs.items():
            status['cron_jobs'][name] = {
                'enabled': job.enabled,
                'interval': job.interval,
                'last_run': job.last_run.isoformat() if job.last_run else None,
                'next_run': job.next_run.isoformat() if job.next_run else None,
                'alive': job._thread.is_alive() if job._thread else False
            }
        return status


# ── Worker de Cola Generico ──
class QueueWorker:
    """Worker que procesa tareas de un canal especifico."""
    def __init__(self, channel: str, handler: Callable, num_workers: int = 1):
        self.channel = channel
        self.handler = handler
        self.num_workers = num_workers
        self._workers: list = []
        self._stop = threading.Event()

    def start(self):
        """Inicia los workers."""
        self._stop.clear()
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name='worker-' + self.channel + '-' + str(i))
            self._workers.append(t)
            t.start()
        logger.info("%d worker(s) iniciados para canal '%s'", self.num_workers, self.channel)

    def stop(self):
        """Detiene todos los workers."""
        self._stop.set()
        for t in self._workers:
            t.join(timeout=5)
        self._workers.clear()
        logger.info("Workers del canal '%s' detenidos", self.channel)

    def _worker_loop(self):
        while not self._stop.is_set():
            task = subscribe(self.channel, timeout=POLL_INTERVAL)
            if task:
                try:
                    result = self.handler(task['payload'])
                    acknowledge(task['id'], result=result)
                except Exception as e:
                    acknowledge(task['id'], error=str(e))


# ── Ejemplo de uso ──
if __name__ == '__main__':
    scheduler = Scheduler()

    def ejemplo_tarea():
        logger.info("Tarea programada ejecutandose")

    scheduler.register_cron('recon_healthcheck', 60, ejemplo_tarea)
    scheduler.start_all()

    publish('osint:scan', {'target': 'example.com', 'tool': 'phone'})

    try:
        while True:
            time.sleep(10)
            logger.info("Tareas pendientes: %d", get_pending_count())
    except KeyboardInterrupt:
        scheduler.stop_all()