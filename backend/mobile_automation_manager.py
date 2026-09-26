"""Mobile Automation Manager - Automatización multi-app para Android."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AppType(Enum):
    ROLLERCOIN = "rollercoin"
    REWARD_APP = "reward_app"
    SURVEY_APP = "survey_app"
    GAME_REWARD = "game_reward"
    CASHBACK_APP = "cashback_app"
    MICRO_TASK = "micro_task"


@dataclass
class RewardApp:
    name: str
    package_name: str
    app_type: AppType
    estimated_earning_per_hour: float
    automation_supported: bool
    popularity_score: float
    last_earnings: float = 0.0
    last_run: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "package": self.package_name,
            "type": self.app_type.value,
            "earning_per_hour": self.estimated_earning_per_hour,
            "automation_supported": self.automation_supported,
            "popularity": self.popularity_score,
            "last_earnings": self.last_earnings,
            "last_run": self.last_run,
            "enabled": self.enabled,
        }


class MobileAutomationManager:
    def __init__(self, db=None, adb_connector=None) -> None:
        self.db = db
        self.adb = adb_connector
        self.known_apps = self._init_known_apps()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.daily_earnings = 0.0
        self.total_earnings = 0.0
        self.apps_running: List[str] = []

    def _init_known_apps(self) -> List[RewardApp]:
        return [
            RewardApp(
                name="Rollercoin",
                package_name="com.rollercoin.android",
                app_type=AppType.ROLLERCOIN,
                estimated_earning_per_hour=2.50,
                automation_supported=True,
                popularity_score=95.0,
            ),
            RewardApp(
                name="Mistplay",
                package_name="com.mistplay.application",
                app_type=AppType.GAME_REWARD,
                estimated_earning_per_hour=0.75,
                automation_supported=True,
                popularity_score=88.0,
            ),
            RewardApp(
                name="Google Opinion Rewards",
                package_name="com.google.android.apps.paidtasks",
                app_type=AppType.SURVEY_APP,
                estimated_earning_per_hour=0.30,
                automation_supported=False,
                popularity_score=92.0,
                enabled=False,
            ),
            RewardApp(
                name="TaskRabbit",
                package_name="com.taskrabbit.droid",
                app_type=AppType.MICRO_TASK,
                estimated_earning_per_hour=1.20,
                automation_supported=True,
                popularity_score=85.0,
            ),
            RewardApp(
                name="Cashyy",
                package_name="com.cashyy",
                app_type=AppType.CASHBACK_APP,
                estimated_earning_per_hour=0.50,
                automation_supported=True,
                popularity_score=75.0,
            ),
            RewardApp(
                name="FeaturePoints",
                package_name="com.featurepoints.app",
                app_type=AppType.REWARD_APP,
                estimated_earning_per_hour=0.60,
                automation_supported=True,
                popularity_score=82.0,
            ),
        ]

    async def scan_device_apps(self) -> List[RewardApp]:
        if not self.adb:
            return self.known_apps
        try:
            installed = await self.adb.get_installed_packages()
            detected = []
            for app in self.known_apps:
                if app.package_name in installed:
                    detected.append(app)
                    print("Mobile: detectada %s" % app.name)
            return detected
        except Exception as e:
            print("Mobile: error escaneando apps: %s" % e)
            return self.known_apps

    async def start_automation_loop(self) -> None:
        print("Mobile: iniciando automation loop")
        while True:
            try:
                available_apps = await self.scan_device_apps()
                available_apps.sort(key=lambda x: x.estimated_earning_per_hour, reverse=True)
                tasks = []
                for app in available_apps[:3]:
                    if app.enabled and app.automation_supported:
                        task = asyncio.create_task(self._run_app_automation(app))
                        tasks.append(task)
                await asyncio.gather(*tasks, return_exceptions=True)
                await self._report_daily_earnings()
                await asyncio.sleep(1800)
            except Exception as e:
                print("Mobile: error en automation loop: %s" % e)
                await asyncio.sleep(300)

    async def _run_app_automation(self, app: RewardApp) -> float:
        print("Mobile: ejecutando %s" % app.name)
        try:
            if self.adb:
                await self.adb.launch_app(app.package_name)
                await asyncio.sleep(2)
            earnings = 0.0
            if app.app_type == AppType.ROLLERCOIN:
                earnings = await self._automate_rollercoin()
            elif app.app_type == AppType.GAME_REWARD:
                earnings = await self._automate_game_reward(app)
            elif app.app_type == AppType.MICRO_TASK:
                earnings = await self._automate_micro_task(app)
            elif app.app_type == AppType.CASHBACK_APP:
                earnings = await self._automate_cashback(app)
            app.last_earnings = earnings
            app.last_run = datetime.now().isoformat()
            self.daily_earnings += earnings
            if self.adb:
                await self.adb.close_app(app.package_name)
            print("Mobile: %s +$%.2f" % [app.name, earnings])
            return earnings
        except Exception as e:
            print("Mobile: error en %s: %s" % [app.name, e])
            return 0.0

    async def _automate_rollercoin(self) -> float:
        clicks = 0
        for _ in range(10):
            if self.adb and await self.adb.find_element_by_text("Claim"):
                await self.adb.click_by_text("Claim")
                clicks += 1
                await asyncio.sleep(1)
            else:
                break
        return clicks * 0.25

    async def _automate_game_reward(self, app: RewardApp) -> float:
        if self.adb and await self.adb.find_element_by_resource_id("reward_button"):
            await self.adb.click_by_resource_id("reward_button")
            await asyncio.sleep(2)
            if self.adb and await self.adb.find_element_by_text("Confirm"):
                await self.adb.click_by_text("Confirm")
                return 0.75
        return 0.0

    async def _automate_micro_task(self, app: RewardApp) -> float:
        if self.adb and await self.adb.find_element_by_resource_id("start_task_button"):
            await self.adb.click_by_resource_id("start_task_button")
            await asyncio.sleep(30)
            if self.adb and await self.adb.find_element_by_text("Submit"):
                await self.adb.click_by_text("Submit")
                return 1.20
        return 0.0

    async def _automate_cashback(self, app: RewardApp) -> float:
        if self.adb and await self.adb.find_element_by_text("My Rewards"):
            await self.adb.click_by_text("My Rewards")
            return await self._extract_reward_amount()
        return 0.0

    async def _extract_reward_amount(self) -> float:
        return 0.5

    async def _report_daily_earnings(self) -> None:
        try:
            if self.db:
                self.db.add_mobile_earnings(
                    amount=self.daily_earnings,
                    apps_count=len(self.apps_running),
                    timestamp=datetime.now().isoformat(),
                )
            print("Mobile: ganancias del día $%.2f" % self.daily_earnings)
            self.daily_earnings = 0.0
        except Exception as e:
            print("Mobile: error reportando earnings: %s" % e)

    def get_apps_status(self) -> Dict[str, Any]:
        return {
            "apps": [app.to_dict() for app in self.known_apps],
            "daily_earnings": self.daily_earnings,
            "total_earnings": self.total_earnings,
            "active_apps": len(self.apps_running),
            "status": "running" if self.active_tasks else "idle",
        }

    async def enable_app(self, app_name: str) -> bool:
        for app in self.known_apps:
            if app.name.lower() == app_name.lower():
                app.enabled = True
                print("Mobile: %s habilitada" % app_name)
                return True
        return False

    async def disable_app(self, app_name: str) -> bool:
        for app in self.known_apps:
            if app.name.lower() == app_name.lower():
                app.enabled = False
                print("Mobile: %s deshabilitada" % app_name)
                return True
        return False


class AndroidADBConnector:
    def __init__(self, device_id: str = None) -> None:
        self.device_id = device_id

    async def get_installed_packages(self) -> List[str]:
        return []

    async def launch_app(self, package_name: str) -> None:
        pass

    async def close_app(self, package_name: str) -> None:
        pass

    async def click_by_text(self, text: str) -> None:
        pass

    async def click_by_resource_id(self, resource_id: str) -> None:
        pass

    async def find_element_by_text(self, text: str) -> bool:
        return False

    async def find_element_by_resource_id(self, resource_id: str) -> bool:
        return False

    async def screenshot(self) -> bytes:
        return b""
