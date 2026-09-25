import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class StableDiffusionConnector(ConnectorBase):
    def __init__(self, api_url: str = "", api_key: str = "") -> None:
        super().__init__("stable_diffusion")
        self.api_url = api_url or os.environ.get("SD_API_URL", "http://localhost:7860")
        self.api_key = api_key or os.environ.get("SD_API_KEY", "")
        self._queue: List[Dict[str, Any]] = []
        self._completed: List[Dict[str, Any]] = []

    async def verify_connection(self) -> bool:
        return True

    async def _request(self, endpoint: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = (
            f"{self.api_url}/api/{endpoint}"
            if not self.api_url.endswith("/")
            else f"{self.api_url}api/{endpoint}"
        )
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def generate_image(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        negative_prompt: str = "",
    ) -> Dict[str, Any]:
        async def _do():
            body = {
                "prompt": prompt,
                "width": width,
                "height": height,
                "steps": steps,
                "negative_prompt": negative_prompt,
                "seed": -1,
            }
            return await asyncio.to_thread(self._request, "txt2img", body)

        return await self.retry_with_exponential_backoff(_do)

    async def upscale(self, image_path: str, scale: int = 2) -> Dict[str, Any]:
        async def _do():
            body = {"image": image_path, "scale": scale, "mode": "upscale"}
            return await asyncio.to_thread(self._request, "extra-single-image", body)

        return await self.retry_with_exponential_backoff(_do)

    async def inpaint(self, image_path: str, mask_path: str, prompt: str) -> Dict[str, Any]:
        async def _do():
            body = {"init_images": [image_path], "mask": mask_path, "prompt": prompt}
            return await asyncio.to_thread(self._request, "img2img", body)

        return await self.retry_with_exponential_backoff(_do)

    async def queue_generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        job_id = f"sd_{kwargs.get('prompt', prompt)[:20]}_{len(self._queue)}"
        job = {
            "id": job_id,
            "prompt": prompt,
            "status": "queued",
            "kwargs": kwargs,
            "created_at": None,
        }
        self._queue.append(job)
        asyncio.create_task(self._process_queue(job_id))
        return {"queued": True, "job_id": job_id, "status": "queued"}

    async def _process_queue(self, job_id: str) -> None:
        for job in self._queue:
            if job["id"] == job_id:
                job["status"] = "processing"
                try:
                    result = await self.generate_image(job["prompt"], **job.get("kwargs", {}))
                    job["status"] = "completed"
                    job["result"] = result
                    self._completed.append(job)
                except Exception as exc:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                break
