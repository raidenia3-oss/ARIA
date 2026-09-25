from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

from backend.automation.engine import AutomationEngine, AutomationRule, automation_engine
from backend.automation.scheduler import (
    CronParseError,
    ResourceConflictResolver,
    ScheduledTask,
    SchedulerEngine,
    TaskPersistence,
    TaskSchedulerEngine,
    enable_autostart,
    get_scheduler,
    next_cron_fire,
    parse_cron,
    reset_scheduler,
)
from backend.automation.scheduler import router as scheduler_router
from backend.automation.scheduler import validate_cron

__all__ = [
    "AutomationEngine",
    "AutomationRule",
    "automation_engine",
    # Scheduler (Bloque 67)
    "CronParseError",
    "ResourceConflictResolver",
    "ScheduledTask",
    "TaskPersistence",
    "TaskSchedulerEngine",
    "SchedulerEngine",
    "get_scheduler",
    "reset_scheduler",
    "validate_cron",
    "parse_cron",
    "next_cron_fire",
    "scheduler_router",
    "enable_autostart",
]
