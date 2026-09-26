import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class GitHubConnector(ConnectorBase):
    def __init__(self, token: str = "") -> None:
        super().__init__("github")
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.base_url = "https://api.github.com"

    async def verify_connection(self) -> bool:
        return bool(self.token)

    async def _request(self, method: str, path: str, body: Optional[Dict] = None) -> Dict[str, Any]:
        import urllib.request

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"token {self.token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._circuit_open = True
            self._circuit_opened_at = asyncio.get_event_loop().time()
            raise

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        async def _do():
            return await asyncio.to_thread(self._request, "GET", f"/repos/{owner}/{repo}", None)

        return await self.retry_with_exponential_backoff(_do)

    async def create_pr(
        self, owner: str, repo: str, title: str, body: str, head: str, base: str
    ) -> Dict[str, Any]:
        async def _do():
            pr_body = {"title": title, "body": body, "head": head, "base": base}
            return await asyncio.to_thread(
                self._request, "POST", f"/repos/{owner}/{repo}/pulls", pr_body
            )

        return await self.retry_with_exponential_backoff(_do)

    async def manage_issues(
        self, owner: str, repo: str, action: str, issue_number: Optional[int] = None, **kwargs
    ) -> Dict[str, Any]:
        async def _do():
            if action == "create":
                return await asyncio.to_thread(
                    self._request, "POST", f"/repos/{owner}/{repo}/issues", kwargs
                )
            elif action == "update" and issue_number:
                return await asyncio.to_thread(
                    self._request, "PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", kwargs
                )
            elif action == "list":
                return await asyncio.to_thread(
                    self._request, "GET", f"/repos/{owner}/{repo}/issues", kwargs
                )
            elif action == "close" and issue_number:
                return await asyncio.to_thread(
                    self._request,
                    "PATCH",
                    f"/repos/{owner}/{repo}/issues/{issue_number}",
                    {"state": "closed"},
                )
            return {"error": f"Unknown action: {action}"}

        return await self.retry_with_exponential_backoff(_do)

    async def deploy_workflow(
        self, owner: str, repo: str, workflow_id: str, branch: str = "main"
    ) -> Dict[str, Any]:
        async def _do():
            body = {"ref": branch, "workflow_id": workflow_id}
            return await asyncio.to_thread(
                self._request,
                "POST",
                f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
                body,
            )

        return await self.retry_with_exponential_backoff(_do)

    async def read_file(
        self, owner: str, repo: str, path: str, branch: str = "main"
    ) -> Dict[str, Any]:
        async def _do():
            return await asyncio.to_thread(
                self._request, "GET", f"/repos/{owner}/{repo}/contents/{path}?ref={branch}", None
            )

        return await self.retry_with_exponential_backoff(_do)
