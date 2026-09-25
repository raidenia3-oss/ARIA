import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class HuggingFaceConnector(ConnectorBase):
    def __init__(
        self, token: str = "", base_url: str = "https://api-inference.huggingface.co"
    ) -> None:
        super().__init__("huggingface")
        self.token = token or os.environ.get("HF_TOKEN", "")
        self.base_url = base_url
        self._cache: Dict[str, Any] = {}

    async def verify_connection(self) -> bool:
        return True

    async def _request(
        self, method: str, path: str, body: Optional[Dict] = None, headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else {}
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def list_models(self, filter: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        async def _do():
            import urllib.request

            url = f"{self.base_url}/models"
            from urllib.parse import urlencode

            if filter:
                url += f"?{urlencode({'filter': filter, 'limit': limit})}"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Authorization", f"Bearer {self.token}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else []

        return await self.retry_with_exponential_backoff(_do)

    async def run_inference(
        self, model_id: str, inputs: str, parameters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        async def _do():
            body = {"inputs": inputs}
            if parameters:
                body["parameters"] = parameters
            return await asyncio.to_thread(self._request, "POST", f"/models/{model_id}", body)

        return await self.retry_with_exponential_backoff(_do)

    async def streaming_inference(self, model_id: str, inputs: str) -> List[Dict[str, Any]]:
        results = []
        import urllib.request

        url = f"{self.base_url}/models/{model_id}"
        data = json.dumps({"inputs": inputs}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    if line.strip():
                        try:
                            results.append(json.loads(line.decode("utf-8").strip()))
                        except json.JSONDecodeError:
                            pass
        except Exception as exc:
            return [{"error": str(exc)}]
        return results

    async def fine_tune(
        self, model_id: str, dataset: str, epochs: int = 3, learning_rate: float = 5e-5
    ) -> Dict[str, Any]:
        async def _do():
            body = {
                "model": model_id,
                "dataset": dataset,
                "training_parameters": {"epochs": epochs, "learning_rate": learning_rate},
            }
            return await asyncio.to_thread(self._request, "POST", "/models/fine-tune", body)

        return await self.retry_with_exponential_backoff(_do)

    async def upload_dataset(
        self, repo_id: str, files: List[str], license: str = "mit"
    ) -> Dict[str, Any]:
        async def _do():
            body = {"repo_id": repo_id, "files": files, "license": license}
            return await asyncio.to_thread(self._request, "POST", "/datasets", body)

        return await self.retry_with_exponential_backoff(_do)
