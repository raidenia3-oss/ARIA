"""
Shadow-Core Tactical Queue — Sistema Honker-Style Pub/Sub sobre SQLite
Cola de tareas ligeras sin dependencias externas (Redis/Celery).
Tabla 'tactical_queue' con daemon que lee y dispara comandos.
"""
import os
import sys
import time
import json
import sqlite3
import logging
import threading
from datetime import datetime
from typing import Optional, Callable, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [TacticalQueue] %(levelname)s %(message)s')
logger = logging.getLogger('tactical_queue')

# ── Configuracion ──
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
DEFAULT_NODE_REGISTRY: dict = {}


def init_tactical_db():
    """Crea la tabla tactical_queue si no existe."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tactical_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            command TEXT NOT NULL,
            target TEXT,
            params TEXT,
            priority INTEGER DEFAULT 0,
            scheduled_at TEXT,
            status TEXT DEFAULT "queued",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tactical_status ON tactical_queue(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tactical_channel ON tactical_queue(channel)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tactical_scheduled ON tactical_queue(scheduled_at)')
    conn.commit()
    conn.close()
    logger.info("Base de datos tactical_queue inicializada: %s", DB_PATH)


def enqueue_command(channel: str, command: str, target: str = "",
                   params: dict = None, priority: int = 0,
                   delay_seconds: int = 0) -> int:
    """Encola un comando en la tactical_queue."""
    scheduled_at = (datetime.now().timestamp() + delay_seconds)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO tactical_queue (channel, command, target, params, priority, scheduled_at) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (channel, command, target, json.dumps(params or {}), priority, scheduled_at)
    )
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    logger.info("Tarea #%d encolada en canal '%s': %s", task_id, channel, command)
    return task_id


def get_pending_commands(channel: Optional[str] = None) -> list:
    """Retorna comandos encolados/pendientes."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now_ts = datetime.now().timestamp()
    if channel:
        c.execute(
            'SELECT id, channel, command, target, params, priority FROM tactical_queue '
            'WHERE status = "queued" AND scheduled_at <= ? AND channel = ? '
            'ORDER BY priority DESC, id ASC',
            (now_ts, channel)
        )
    else:
        c.execute(
            'SELECT id, channel, command, target, params, priority FROM tactical_queue '
            'WHERE status = "queued" AND scheduled_at <= ? '
            'ORDER BY priority DESC, id ASC',
            (now_ts,)
        )
    rows = c.fetchall()
    conn.close()
    return [
        {
            'id': r[0], 'channel': r[1], 'command': r[2],
            'target': r[3], 'params': json.loads(r[4] or '{}'),
            'priority': r[5]
        }
        for r in rows
    ]


def mark_running(task_id: int):
    """Marca un comando como ejecutándose."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'UPDATE tactical_queue SET status = "running", started_at = ? WHERE id = ?',
        (datetime.now().isoformat(), task_id)
    )
    conn.commit()
    conn.close()


def mark_completed(task_id: int, result: Any = None, error: Optional[str] = None):
    """Marca un comando como completado/fallido."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    status = 'failed' if error else 'completed'
    c.execute(
        'UPDATE tactical_queue SET status = ?, completed_at = ?, result = ?, error = ? WHERE id = ?',
        (status, datetime.now().isoformat(), json.dumps(result) if result else None, error, task_id)
    )
    conn.commit()
    conn.close()


def get_tactical_stats() -> dict:
    """Retorna estadísticas de la cola."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    stats = {}
    for status in ['queued', 'running', 'completed', 'failed']:
        c.execute('SELECT COUNT(*) FROM tactical_queue WHERE status = ?', (status,))
        stats[status] = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT channel) FROM tactical_queue')
    stats['channels'] = c.fetchone()[0]
    conn.close()
    return stats


class TacticalWorker:
    """
    Demonio en segundo plano que lee tactical_queue,
    dispara handlers registrados y actualiza estados.
    """
    def __init__(self, poll_interval: int = 2):
        self.handlers: dict = {}  # {channel: Callable}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.poll_interval = poll_interval
        self._running = False

    def register_handler(self, channel: str, handler: Callable):
        """Registra un handler para procesar tareas de un canal."""
        self.handlers[channel] = handler
        logger.info("Handler registrado para canal '%s'", channel)

    def start(self):
        """Inicia el worker daemon."""
        if self._thread and self._thread.is_alive():
            return
        init_tactical_db()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='tactical-worker')
        self._thread.start()
        self._running = True
        logger.info("TacticalWorker iniciado (poll cada %ds)", self.poll_interval)

    def stop(self):
        """Detiene el worker."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._running = False
        logger.info("TacticalWorker detenido")

    def _run_loop(self):
        while not self._stop.is_set():
            try:
                tasks = get_pending_commands()
                for task in tasks:
                    channel = task['channel']
                    handler = self.handlers.get(channel)
                    if handler:
                        mark_running(task['id'])
                        try:
                            result = handler(task)
                            mark_completed(task['id'], result=result)
                        except Exception as e:
                            mark_completed(task['id'], error=str(e))
                    else:
                        # No handler: marcar error y log
                        logger.warning("Sin handler para canal '%s' (task #%d)", channel, task['id'])
                        mark_completed(task['id'], error='no handler')
            except Exception as e:
                logger.error("Error en worker loop: %s", e)
            self._stop.wait(self.poll_interval)

    def get_status(self) -> dict:
        return {
            'running': self._running,
            'channels': list(self.handlers.keys()),
            'stats': get_tactical_stats()
        }


# ── Handlers de ejemplo (registrados en runtime) ──
def example_handler_scan(task: dict) -> dict:
    """Handler de ejemplo para tareas de escaneo."""
    logger.info("Ejecutando scan: %s target=%s", task['command'], task['target'])
    time.sleep(0.1)  # Simular trabajo
    return {'success': True, 'target': task['target']}


def example_handler_recon(task: dict) -> dict:
    """Handler de ejemplo para tareas de reconocimiento."""
    logger.info("Ejecutando recon: %s", task['command'])
    time.sleep(0.1)
    return {'success': True, 'data': 'recon_complete'}


# ── MAIN: Ejecutar como demonio ──
if __name__ == '__main__':
    print("=" * 60)
    print("AURA SHADOW-CORE TACTICAL QUEUE (Honker-Style)")
    print("=" * 60)

    worker = TacticalWorker()
    worker.register_handler('osint:scan', example_handler_scan)
    worker.register_handler('recon:dns', example_handler_recon)
    worker.register_handler('recon:port', example_handler_scan)
    worker.start()

    print("\nWorker iniciado. Encolando tareas de ejemplo...")
    enqueue_command('osint:scan', 'phone_lookup', '+1234567890', {'source': 'demo'})
    enqueue_command('recon:dns', 'dns_enum', 'example.com', {'threads': 10})
    enqueue_command('recon:port', 'port_scan', '192.168.1.1', {'ports': '1-1000'})

    try:
        while True:
            time.sleep(5)
            stats = get_tactical_stats()
            print("Estadisticas: %s", stats)
    except KeyboardInterrupt:
        worker.stop()