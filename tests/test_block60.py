"""Tests for BLOQUE 60 - AURA Local Self-Evolution, Auto-Patching & Offline Fine-Tuning Engine."""

from __future__ import annotations

import json
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.evolution import (
    DatasetSplit,
    EvolutionEngine,
    FineTuneJob,
    LoRAScheduler,
    PatchRecord,
    PatchStatus,
    get_evolution_engine,
    reset_evolution_engine,
)
from backend.agent.evolution_routes import router


@pytest.fixture
def engine(tmp_path):
    reset_evolution_engine()
    eng = EvolutionEngine(data_dir=tmp_path)
    yield eng
    reset_evolution_engine()


@pytest.fixture
def client(tmp_path):
    reset_evolution_engine()
    _ = EvolutionEngine(data_dir=tmp_path)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_evolution_engine()


class TestLoRAScheduler:
    def test_schedule_job(self, engine):
        entries = [
            {"instruction": "x", "input": "a", "output": "b", "source": "s", "quality_score": 1.0},
            {"instruction": "y", "input": "c", "output": "d", "source": "s", "quality_score": 1.0},
            {"instruction": "z", "input": "e", "output": "f", "source": "s", "quality_score": 1.0},
        ]
        manifest = engine.build_dataset("ds_lora", entries=entries)
        job = engine.lora_scheduler.schedule_job(dataset_id=manifest["dataset_id"])
        assert isinstance(job, FineTuneJob)
        assert job.status == "scheduled"
        assert job.dataset_id == manifest["dataset_id"]

    def test_list_jobs(self, engine):
        entries = [
            {"instruction": "x", "input": "a", "output": "b", "source": "s", "quality_score": 1.0},
            {"instruction": "y", "input": "c", "output": "d", "source": "s", "quality_score": 1.0},
            {"instruction": "z", "input": "e", "output": "f", "source": "s", "quality_score": 1.0},
        ]
        manifest = engine.build_dataset("ds_lora2", entries=entries)
        engine.lora_scheduler.schedule_job(dataset_id=manifest["dataset_id"])
        jobs = engine.lora_scheduler.list_jobs()
        assert len(jobs) == 1

    def test_start_checkpoint_complete(self, engine):
        entries = [
            {"instruction": "x", "input": "a", "output": "b", "source": "s", "quality_score": 1.0},
            {"instruction": "y", "input": "c", "output": "d", "source": "s", "quality_score": 1.0},
            {"instruction": "z", "input": "e", "output": "f", "source": "s", "quality_score": 1.0},
        ]
        manifest = engine.build_dataset("ds_lora3", entries=entries)
        job = engine.lora_scheduler.schedule_job(dataset_id=manifest["dataset_id"])
        engine.lora_scheduler.start_job(job.job_id)
        ck = engine.lora_scheduler.checkpoint_job(job.job_id, metrics={"loss": 0.5})
        assert ck["checkpoint_id"]
        engine.lora_scheduler.complete_job(job.job_id, metrics={"final_loss": 0.4})
        fetched = engine.lora_scheduler.get_job(job.job_id)
        assert fetched.status == "completed"

    def test_fail_job(self, engine):
        entries = [
            {"instruction": "x", "input": "a", "output": "b", "source": "s", "quality_score": 1.0},
            {"instruction": "y", "input": "c", "output": "d", "source": "s", "quality_score": 1.0},
            {"instruction": "z", "input": "e", "output": "f", "source": "s", "quality_score": 1.0},
        ]
        manifest = engine.build_dataset("ds_lora4", entries=entries)
        job = engine.lora_scheduler.schedule_job(dataset_id=manifest["dataset_id"])
        engine.lora_scheduler.fail_job(job.job_id, error="OOM")
        fetched = engine.lora_scheduler.get_job(job.job_id)
        assert fetched.status == "failed"
        assert fetched.error == "OOM"

    def test_estimate_resources(self, engine):
        entries = [
            {"instruction": "x", "input": "a", "output": "b", "source": "s", "quality_score": 1.0},
            {"instruction": "y", "input": "c", "output": "d", "source": "s", "quality_score": 1.0},
            {"instruction": "z", "input": "e", "output": "f", "source": "s", "quality_score": 1.0},
        ]
        manifest = engine.build_dataset("ds_lora5", entries=entries)
        job = engine.lora_scheduler.schedule_job(dataset_id=manifest["dataset_id"])
        est = engine.lora_scheduler.estimate_resources(job.dataset_id)
        assert est["advisory"] is True
        assert est["total_entries"] == 3


class TestRESTEndpoints:
    def test_status(self, client):
        r = client.get("/api/agent/evolution/status")
        assert r.status_code == 200
        data = r.json()
        assert "patches" in data
        assert "datasets" in data
        assert "lora_jobs" in data
        assert data["offline"] is True

    def test_generate_patch_endpoint(self, client, tmp_path):
        target = tmp_path / "sample.py"
        target.write_text("x = 1\n", encoding="utf-8")
        r = client.post(
            "/api/agent/evolution/patch/generate",
            json={
                "target_file": str(target),
                "old_snippet": "x = 1",
                "new_snippet": "x = 2",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"

    def test_build_dataset_endpoint(self, client):
        r = client.post(
            "/api/agent/evolution/dataset/build",
            json={
                "name": "rest_ds",
                "entries": [
                    {
                        "instruction": "a",
                        "input": "x",
                        "output": "y",
                        "source": "s",
                        "quality_score": 1.0,
                    },
                    {
                        "instruction": "b",
                        "input": "x",
                        "output": "y",
                        "source": "s",
                        "quality_score": 1.0,
                    },
                    {
                        "instruction": "c",
                        "input": "x",
                        "output": "y",
                        "source": "s",
                        "quality_score": 1.0,
                    },
                ],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_entries"] == 3

    def test_list_datasets_endpoint(self, client):
        r = client.get("/api/agent/evolution/datasets")
        assert r.status_code == 200
        data = r.json()
        assert "datasets" in data

    def test_schedule_lora_endpoint(self, client):
        build = client.post(
            "/api/agent/evolution/dataset/build",
            json={
                "name": "lora_rest",
                "entries": [
                    {
                        "instruction": "a",
                        "input": "x",
                        "output": "y",
                        "source": "s",
                        "quality_score": 1.0,
                    },
                    {
                        "instruction": "b",
                        "input": "x",
                        "output": "y",
                        "source": "s",
                        "quality_score": 1.0,
                    },
                    {
                        "instruction": "c",
                        "input": "x",
                        "output": "y",
                        "source": "s",
                        "quality_score": 1.0,
                    },
                ],
            },
        )
        ds_id = build.json()["dataset_id"]
        r = client.post(
            "/api/agent/evolution/lora/schedule",
            json={
                "dataset_id": ds_id,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "scheduled"

    def test_list_lora_jobs_endpoint(self, client):
        r = client.get("/api/agent/evolution/lora/jobs")
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data

    def test_logs_endpoint(self, client):
        r = client.get("/api/agent/evolution/logs")
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
