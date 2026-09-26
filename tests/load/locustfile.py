import base64
import json
import logging
import os
import time

from locust import HttpUser, TaskSet, between, events, task

logger = logging.getLogger("locust")

API_KEY = os.getenv("AURA_API_KEY", "test-key")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

SAMPLE_IMAGE_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


class BackendTasks(TaskSet):
    @task(4)
    def health(self):
        with self.client.get("/health", headers=HEADERS, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"health failed: {response.status_code}")

    @task(3)
    def status(self):
        with self.client.get("/api/status", headers=HEADERS, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"status failed: {response.status_code}")

    @task(2)
    def logs(self):
        with self.client.get(
            "/api/logs?service=backend&lines=20", headers=HEADERS, catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"logs failed: {response.status_code}")

    @task(2)
    def metrics(self):
        with self.client.get("/metrics", headers=HEADERS, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"metrics failed: {response.status_code}")

    @task(1)
    def gesture_predict(self):
        payload = {"image_base64": SAMPLE_IMAGE_B64}
        with self.client.post(
            "/api/gesture/predict", json=payload, headers=HEADERS, catch_response=True
        ) as response:
            if response.status_code not in (200, 422):
                response.failure(f"gesture failed: {response.status_code}")

    @task(1)
    def voice_transcribe(self):
        payload = {"audio_base64": SAMPLE_IMAGE_B64}
        with self.client.post(
            "/api/voice/transcribe", json=payload, headers=HEADERS, catch_response=True
        ) as response:
            if response.status_code not in (200, 422):
                response.failure(f"voice failed: {response.status_code}")

    @task(1)
    def restart_service(self):
        with self.client.post(
            "/api/restart", json={"service": "backend"}, headers=HEADERS, catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"restart failed: {response.status_code}")

    @task(1)
    def deploy_service(self):
        with self.client.post(
            "/api/deploy", json={"service": "backend"}, headers=HEADERS, catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"deploy failed: {response.status_code}")


class AuraBackendUser(HttpUser):
    tasks = [BackendTasks]
    wait_time = between(1, 3)
    weight = 1


class AuraAdminUser(HttpUser):
    tasks = [BackendTasks]
    wait_time = between(2, 5)
    weight = 1


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    if exception:
        logger.error("Request failed: %s %s - %s", request_type, name, exception)
