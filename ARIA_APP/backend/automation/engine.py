import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psutil

from backend.automation.models import (
    Action,
    ActionType,
    AutomationRuleModel,
    Trigger,
    TriggerType,
)


class AutomationRule:
    """Regla de automatizacion individual"""

    def __init__(self, rule_id: str, data: AutomationRuleModel):
        self.id = rule_id
        self.name = data.name
        self.description = data.description
        self.trigger = data.trigger
        self.actions = data.actions
        self.enabled = data.enabled
        self.tags = data.tags

        self.created_at = datetime.now()
        self.last_executed = None
        self.execution_count = 0
        self.last_error = None

    def should_execute(self, event: Optional[Dict] = None) -> bool:
        if not self.enabled:
            return False

        if self.trigger.type == TriggerType.ON_TIME:
            return self._check_time_trigger()
        elif self.trigger.type == TriggerType.ON_EVENT:
            return self._check_event_trigger(event)
        elif self.trigger.type == TriggerType.ON_CONDITION:
            return self._check_condition_trigger()
        elif self.trigger.type == TriggerType.ON_STARTUP:
            return self._check_startup_trigger()

        return False

    def _check_time_trigger(self) -> bool:
        now = datetime.now()

        target_hour = self.trigger.hour
        target_minute = self.trigger.minute or 0
        days = self.trigger.days or []

        if target_hour is None:
            return False

        if now.hour != target_hour or now.minute != target_minute:
            return False

        if days:
            day_name = now.strftime("%A").lower()
            if day_name not in [d.lower() for d in days]:
                return False

        if self.last_executed:
            if (now - self.last_executed).total_seconds() < 60:
                return False

        return True

    def _check_event_trigger(self, event: Optional[Dict]) -> bool:
        if not event:
            return False

        if event.get("event") != self.trigger.event:
            return False

        if self.trigger.skill:
            if event.get("skill") != self.trigger.skill:
                return False

        return True

    def _check_condition_trigger(self) -> bool:
        condition = self.trigger.condition
        if not condition:
            return False

        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent
            disk = psutil.disk_usage(os.path.expanduser("~")).percent

            result = eval(
                condition.replace("cpu", str(cpu))
                .replace("memory", str(memory))
                .replace("disk", str(disk))
            )
            return bool(result)
        except Exception as e:
            print(f"[AutomationRule] Error evaluating condition '{condition}': {e}")
            return False

    def _check_startup_trigger(self) -> bool:
        if self.last_executed is None:
            return True
        return False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": (
                self.trigger.model_dump()
                if hasattr(self.trigger, "model_dump")
                else self.trigger.dict()
            ),
            "actions": [
                a.model_dump() if hasattr(a, "model_dump") else a.dict() for a in self.actions
            ],
            "enabled": self.enabled,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "execution_count": self.execution_count,
            "last_error": self.last_error,
        }


class AutomationEngine:
    """Motor de automatizaciones"""

    def __init__(self, rules_file: str = "data/automation_rules.json"):
        self.rules: Dict[str, AutomationRule] = {}
        self.rules_file = Path(rules_file)
        self.monitoring = False
        self.monitor_interval = 60

        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_rules()

    def add_rule(self, rule_data: AutomationRuleModel) -> str:
        import uuid

        rule_id = str(uuid.uuid4())[:8]

        rule = AutomationRule(rule_id, rule_data)
        self.rules[rule_id] = rule
        self.save_rules()

        print(f"[AutomationEngine] Rule '{rule.name}' added with ID {rule_id}")
        return rule_id

    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        return self.rules.get(rule_id)

    def list_rules(self) -> Dict[str, Dict]:
        return {rule_id: rule.to_dict() for rule_id, rule in self.rules.items()}

    def update_rule(self, rule_id: str, rule_data: AutomationRuleModel) -> bool:
        if rule_id not in self.rules:
            return False
        self.rules[rule_id] = AutomationRule(rule_id, rule_data)
        self.save_rules()
        return True

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.save_rules()
            return True
        return False

    def enable_rule(self, rule_id: str, enabled: bool) -> bool:
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled
            self.save_rules()
            return True
        return False

    async def execute_rule(self, rule: AutomationRule) -> bool:
        print(f"[AutomationEngine] Executing rule '{rule.name}'")

        try:
            for action in rule.actions:
                await self._execute_action(action)
            rule.last_executed = datetime.now()
            rule.execution_count += 1
            rule.last_error = None
            return True
        except Exception as e:
            rule.last_error = str(e)
            print(f"[AutomationEngine] Error executing rule '{rule.name}': {e}")
            return False

    async def _execute_action(self, action: Action) -> None:
        if action.type == ActionType.SKILL:
            try:
                from backend.skills.registry import registry

                skill = registry.get_skill(action.skill)
                if skill:
                    await skill(**action.params)
            except Exception:
                print(f"[AutomationEngine] Skill '{action.skill}' not available")

        elif action.type == ActionType.CHAT:
            try:
                from backend.agent.core import ReactLoop
            except Exception:
                try:
                    from backend.agents.react_loop import ReactLoop
                except Exception:
                    ReactLoop = None
            if ReactLoop:
                try:
                    react = ReactLoop.__new__(ReactLoop)
                    react.skill_registry = None
                    react.memory = None
                    react.ai_manager = None
                    if hasattr(react, "run"):
                        react.run(action.message, system_prompt="Eres ARIA, un asistente personal.")
                except Exception as e:
                    print(f"[AutomationEngine] CHAT action error: {e}")
            else:
                print(f"[AutomationEngine] CHAT action: {action.message}")

        elif action.type == ActionType.API_CALL:
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    method = (action.method or "POST").lower()
                    func = getattr(session, method)
                    async with func(action.url, json=action.params) as resp:
                        await resp.text()
            except Exception as e:
                print(f"[AutomationEngine] API_CALL error: {e}")

        elif action.type == ActionType.DELAY:
            await asyncio.sleep(action.seconds or 0)

        elif action.type == ActionType.NOTIFICATION:
            try:
                from plyer import notification

                notification.notify(
                    title=action.title or "ARIA",
                    message=action.body or "",
                    timeout=5,
                )
            except Exception:
                print(f"[AutomationEngine] Notification: {action.title} - {action.body}")

    async def check_and_execute(self, event: Optional[Dict] = None) -> None:
        for rule in self.rules.values():
            if rule.should_execute(event):
                await self.execute_rule(rule)

    async def start_monitoring(self) -> None:
        self.monitoring = True
        print("[AutomationEngine] Monitoring started")

        while self.monitoring:
            try:
                await self.check_and_execute()
                await asyncio.sleep(self.monitor_interval)
            except Exception as e:
                print(f"[AutomationEngine] Monitoring error: {e}")
                await asyncio.sleep(self.monitor_interval)

    def stop_monitoring(self) -> None:
        self.monitoring = False
        print("[AutomationEngine] Monitoring stopped")

    def save_rules(self) -> None:
        try:
            data = {rule_id: rule.to_dict() for rule_id, rule in self.rules.items()}
            with open(self.rules_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"[AutomationEngine] Error saving rules: {e}")

    def load_rules(self) -> None:
        if not self.rules_file.exists():
            return

        try:
            with open(self.rules_file, "r") as f:
                data = json.load(f)

            for rule_id, rule_data in data.items():
                try:
                    model = AutomationRuleModel(
                        name=rule_data["name"],
                        description=rule_data.get("description"),
                        trigger=Trigger(**rule_data["trigger"]),
                        actions=[Action(**a) for a in rule_data["actions"]],
                        enabled=rule_data.get("enabled", True),
                        tags=rule_data.get("tags", []),
                    )
                    self.rules[rule_id] = AutomationRule(rule_id, model)
                except Exception as e:
                    print(f"[AutomationEngine] Error loading rule {rule_id}: {e}")
        except Exception as e:
            print(f"[AutomationEngine] Error loading rules file: {e}")


automation_engine = AutomationEngine()
