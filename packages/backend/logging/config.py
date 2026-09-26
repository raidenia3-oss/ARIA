import logging
import sys

import pythonjsonlogger.jsonlogger
import structlog


def setup_logging(log_level: str = "INFO") -> None:
    normalized_level = log_level.strip().upper()
    if normalized_level not in logging._nameToLevel:
        raise ValueError(f"Unknown log level: {log_level!r}")

    json_formatter = pythonjsonlogger.jsonlogger.JsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    file_handler = logging.FileHandler("logs/aura.log")
    file_handler.setFormatter(json_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(normalized_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
