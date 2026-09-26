"""Logger — Logging centralizado"""

import logging
from pathlib import Path
from datetime import datetime


class Logger:
    """Logger centralizado"""

    def __init__(self, name: str = "ARIA"):
        self.name = name
        self.log_dir = Path('ARIA_v4/AURA_APP/logs')
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # File handler
        log_file = self.log_dir / f"{datetime.now().strftime('%Y%m%d')}.log"
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def info(self, msg: str) -> None:
        self.logger.info(msg)

    def error(self, msg: str) -> None:
        self.logger.error(msg)

    def warning(self, msg: str) -> None:
        self.logger.warning(msg)

    def debug(self, msg: str) -> None:
        self.logger.debug(msg)


logger = Logger()
