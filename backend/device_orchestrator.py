"""Device orchestrator for AURA."""

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import psutil

from backend.database import SessionLocal
from backend.models import Device as DeviceModel
from backend.models import DistributedTask as DistributedTaskModel


class DeviceType(str, Enum):
    SERVER = "server"
    PC = "pc"
    MOBILE = "mobile"
    WEB = "web"


class DeviceCapability(str, Enum):
    NARRATIVE = "narrative_generation"
    MOBILE_AUTO = "mobile_automation"
    ANALYTICS = "analytics"
    GPU_PROCESSING = "gpu_processing"
    TRAINING = "federated_training"


@dataclass
class DeviceProfile:
    device_id: str
    device_type: str
    device_name: str
    ip_address: str
    cpu_cores: int
    ram_gb: float
    gpu_available: bool
    capabilities: List[str]
    is_online: bool
    last_heartbeat: str
    load_percent: float
    battery_percent: Optional[float]
    bandwidth_mbps: float
    uptime_seconds: int
    version: str


@dataclass
class DistributedTask:
    task_id: str
    task_type: str
    priority: int
    required_capability: str
    status: str
    assigned_device: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[Dict[str, Any]]
    payload: Dict[str, Any]


class DeviceOrchestrator:
    def __init__(self, db_session_factory) -> None:
        self.db_session_factory = db_session_factory
        self.devices: Dict[str, DeviceProfile] = {}
        self.connected_devices: Dict[str, Any] = {}
        self.task_queue: List[DistributedTask] = []

    async def register_device(
        self,
        device_id: str,
        device_type: str,
        device_name: str,
        ip_address: str,
    ) -> DeviceProfile:
        dtype = DeviceType(device_type)
        if dtype == DeviceType.PC:
            profile = await self._measure_pc_capabilities(device_id, device_name, ip_address)
        elif dtype == DeviceType.MOBILE:
            profile = await self._measure_mobile_capabilities(device_id, device_name, ip_address)
        elif dtype == DeviceType.WEB:
            profile = await self._measure_web_capabilities(device_id, device_name, ip_address)
        else:
            profile = await self._measure_server_capabilities(device_id, device_name, ip_address)

        self.devices[device_id] = profile
        await self._persist_device(profile)
        print(f"Device registered: {device_name} ({device_type})")
        return profile

    async def _measure_pc_capabilities(self, device_id: str, device_name: str, ip: str) -> DeviceProfile:
        cpu_cores = psutil.cpu_count() or 4
        ram_gb = float(psutil.virtual_memory().total) / (1024 ** 3)
        gpu_available = await self._detect_gpu()
        return DeviceProfile(
            device_id=device_id,
            device_type=DeviceType.PC.value,
            device_name=device_name,
            ip_address=ip,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
            gpu_available=gpu_available,
            capabilities=[DeviceCapability.NARRATIVE.value, DeviceCapability.TRAINING.value, DeviceCapability.ANALYTICS.value]
            + ([DeviceCapability.GPU_PROCESSING.value] if gpu_available else []),
            is_online=True,
            last_heartbeat=datetime.now().isoformat(),
            load_percent=float(psutil.cpu_percent()),
            battery_percent=None,
            bandwidth_mbps=1000.0,
            uptime_seconds=int(psutil.boot_time()),
            version="3.1",
        )

    async def _measure_mobile_capabilities(self, device_id: str, device_name: str, ip: str) -> DeviceProfile:
        return DeviceProfile(
            device_id=device_id,
            device_type=DeviceType.MOBILE.value,
            device_name=device_name,
            ip_address=ip,
            cpu_cores=4,
            ram_gb=4.0,
            gpu_available=True,
            capabilities=[DeviceCapability.MOBILE_AUTO.value, DeviceCapability.ANALYTICS.value],
            is_online=True,
            last_heartbeat=datetime.now().isoformat(),
            load_percent=30.0,
            battery_percent=75.0,
            bandwidth_mbps=100.0,
            uptime_seconds=3600,
            version="3.1",
        )

    async def _measure_web_capabilities(self, device_id: str, device_name: str, ip: str) -> DeviceProfile:
        return DeviceProfile(
            device_id=device_id,
            device_type=DeviceType.WEB.value,
            device_name=device_name,
            ip_address=ip,
            cpu_cores=1,
            ram_gb=0.0,
            gpu_available=False,
            capabilities=[DeviceCapability.ANALYTICS.value],
            is_online=True,
            last_heartbeat=datetime.now().isoformat(),
            load_percent=0.0,
            battery_percent=None,
            bandwidth_mbps=10.0,
            uptime_seconds=0,
            version="3.1",
        )

    async def _measure_server_capabilities(self, device_id: str, device_name: str, ip: str) -> DeviceProfile:
        return DeviceProfile(
            device_id=device_id,
            device_type=DeviceType.SERVER.value,
            device_name=device_name,
            ip_address=ip,
            cpu_cores=4,
            ram_gb=2.0,
            gpu_available=False,
            capabilities=[DeviceCapability.NARRATIVE.value, DeviceCapability.ANALYTICS.value, DeviceCapability.TRAINING.value],
            is_online=True,
            last_heartbeat=datetime.now().isoformat(),
            load_percent=float(psutil.cpu_percent()),
            battery_percent=None,
            bandwidth_mbps=100.0,
            uptime_seconds=int(psutil.boot_time()),
            version="3.1",
        )

    async def _detect_gpu(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    async def submit_task(self, task: DistributedTask) -> str:
        self.task_queue.append(task)
        await self._persist_task(task)
        asyncio.create_task(self._schedule_tasks())
        return task.task_id

    async def _schedule_tasks(self) -> None:
        while self.task_queue:
            task = self.task_queue[0]
            best_device = await self._find_best_device_for_task(task)
            if best_device:
                await self._assign_task(task, best_device)
                self.task_queue.pop(0)
            else:
                break

    async def _find_best_device_for_task(self, task: DistributedTask) -> Optional[str]:
        candidates: List[Tuple[str, float]] = []
        for device_id, device in self.devices.items():
            if (
                device.is_online
                and task.required_capability in device.capabilities
                and device.load_percent < 80
            ):
                score = max(0.0, 100.0 - device.load_percent)
                if task.task_type == "narrative" and DeviceCapability.GPU_PROCESSING.value in device.capabilities:
                    score += 50.0
                candidates.append((device_id, score))
        if not candidates:
            return None
        best = max(candidates, key=lambda x: x[1])
        return best[0]

    async def _assign_task(self, task: DistributedTask, device_id: str) -> None:
        task.assigned_device = device_id
        task.status = "running"
        task.started_at = datetime.now().isoformat()
        await self._persist_task(task)
        print(f"Task {task.task_id} assigned to {device_id}")

    async def report_task_completion(self, task_id: str, device_id: str, result: Dict[str, Any]) -> None:
        db = self.db_session_factory()
        try:
            row = db.query(DistributedTaskModel).filter(DistributedTaskModel.task_id == task_id).first()
            if row:
                row.status = "completed"
                row.completed_at = datetime.now().timestamp()
                row.result = json.dumps(result, ensure_ascii=False)
                db.commit()
        finally:
            db.close()
        print(f"Task {task_id} completed on {device_id}")

    async def get_cluster_status(self) -> Dict[str, Any]:
        online_devices = [d for d in self.devices.values() if d.is_online]
        total_cpu_cores = sum(d.cpu_cores for d in online_devices)
        total_ram_gb = sum(d.ram_gb for d in online_devices)
        avg_load = sum(d.load_percent for d in online_devices) / len(online_devices) if online_devices else 0.0
        pending_tasks = sum(1 for t in self.task_queue if t.status == "pending")
        running_tasks = sum(1 for t in self.task_queue if t.status == "running")
        return {
            "online_devices": len(online_devices),
            "total_devices": len(self.devices),
            "total_cpu_cores": total_cpu_cores,
            "total_ram_gb": total_ram_gb,
            "average_load_percent": avg_load,
            "pending_tasks": pending_tasks,
            "running_tasks": running_tasks,
            "devices": [
                {
                    "id": d.device_id,
                    "name": d.device_name,
                    "type": d.device_type,
                    "cpu_cores": d.cpu_cores,
                    "ram_gb": d.ram_gb,
                    "load_percent": d.load_percent,
                    "battery_percent": d.battery_percent,
                    "is_online": d.is_online,
                }
                for d in online_devices
            ],
        }

    async def _persist_device(self, profile: DeviceProfile) -> None:
        db = self.db_session_factory()
        try:
            row = DeviceModel(
                device_id=profile.device_id,
                device_type=profile.device_type,
                device_name=profile.device_name,
                ip_address=profile.ip_address,
                cpu_cores=profile.cpu_cores,
                ram_gb=profile.ram_gb,
                gpu_available=profile.gpu_available,
                capabilities=",".join(profile.capabilities),
                is_online=profile.is_online,
                last_heartbeat=datetime.fromisoformat(profile.last_heartbeat).timestamp(),
                load_percent=profile.load_percent,
                battery_percent=profile.battery_percent,
                bandwidth_mbps=profile.bandwidth_mbps,
                uptime_seconds=profile.uptime_seconds,
                version=profile.version,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    async def _persist_task(self, task: DistributedTask) -> None:
        db = self.db_session_factory()
        try:
            row = DistributedTaskModel(
                task_id=task.task_id,
                task_type=task.task_type,
                priority=task.priority,
                required_capability=task.required_capability,
                status=task.status,
                assigned_device=task.assigned_device,
                created_at=datetime.fromisoformat(task.created_at).timestamp(),
                started_at=datetime.fromisoformat(task.started_at).timestamp() if task.started_at else None,
                completed_at=datetime.fromisoformat(task.completed_at).timestamp() if task.completed_at else None,
                result=json.dumps(task.result, ensure_ascii=False) if task.result else None,
                payload=json.dumps(task.payload, ensure_ascii=False),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
