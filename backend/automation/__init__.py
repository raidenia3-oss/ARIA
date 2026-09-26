from backend.automation.engine import AutomationEngine, AutomationRule, automation_engine
from backend.automation.watchdog import (
    RuntimeWatchdog,
    ProcessHealthMonitor,
    SessionCheckpointManager,
    WatchdogPolicy,
    WatchdogEvent,
    WatchdogStatus,
    ProcessHealth,
    SessionCheckpoint,
    HealthStatus,
    RecoveryAction,
    get_watchdog,
    reset_watchdog,
)
from backend.automation.scheduler import (
    CronParseError,
    ResourceConflictResolver,
    ScheduledTask,
    TaskPersistence,
    TaskSchedulerEngine,
    SchedulerEngine,
    get_scheduler,
    next_cron_fire,
    parse_cron,
    reset_scheduler,
    validate_cron,
    router as scheduler_router,
    enable_autostart,
)

__all__ = [
    "AutomationEngine", "AutomationRule", "automation_engine",
    "RuntimeWatchdog", "ProcessHealthMonitor", "SessionCheckpointManager",
    "WatchdogPolicy", "WatchdogEvent", "WatchdogStatus", "ProcessHealth",
    "SessionCheckpoint", "HealthStatus", "RecoveryAction",
    "get_watchdog", "reset_watchdog",
    "CronParseError", "ResourceConflictResolver", "ScheduledTask",
    "TaskPersistence", "TaskSchedulerEngine", "SchedulerEngine",
    "get_scheduler", "next_cron_fire", "parse_cron",
    "reset_scheduler", "validate_cron",
    "scheduler_router", "enable_autostart",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
