import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from .base import ConnectorBase


class GoogleApisConnector(ConnectorBase):
    def __init__(self, credentials: str = "") -> None:
        super().__init__("google_apis")
        self.credentials = credentials or os.environ.get("GOOGLE_CREDENTIALS", "")
        self._gmail_service = None
        self._sheets_service = None
        self._drive_service = None
        self._calendar_service = None
        self._youtube_service = None
        self._docs_service = None

    async def verify_connection(self) -> bool:
        return bool(self.credentials)

    def _build_service(self, service_name: str):
        service_map = {
            "gmail": self._gmail_service,
            "sheets": self._sheets_service,
            "drive": self._drive_service,
            "calendar": self._calendar_service,
            "youtube": self._youtube_service,
            "docs": self._docs_service,
        }
        svc = service_map.get(service_name)
        if svc is None:
            try:
                import google.auth
                from googleapiclient.discovery import build

                creds, _ = google.auth.default()
                svc = build(service_name, "v3", credentials=creds)
                setattr(self, f"_{service_name}_service", svc)
            except Exception:
                svc = None
        return svc

    async def _request_google(
        self, service: str, method: str, endpoint: str, body: Optional[Dict] = None
    ) -> Dict[str, Any]:
        svc = self._build_service(service)
        if not svc:
            return {"fallback": True, "service": service, "message": "Using cached mode"}

        def _do():
            try:
                resource = svc
                for part in endpoint.split("/"):
                    if part:
                        resource = getattr(resource, part)
                if method.upper() == "GET":
                    return (
                        resource().execute()
                        if body is None
                        else resource(q=self._to_query(body)).execute()
                    )
                elif method.upper() == "POST":
                    return resource().execute(body or {})
                elif method.upper() == "PATCH":
                    return resource().execute(body or {})
                elif method.upper() == "DELETE":
                    return resource().execute()
            except Exception as exc:
                return {"error": str(exc)}

        return await asyncio.to_thread(_do)

    def _to_query(self, params: Dict) -> str:
        from urllib.parse import urlencode

        return urlencode({k: str(v) for k, v in params.items() if v is not None})

    async def read_emails(
        self, user_id: str = "me", max_results: int = 10, query: str = ""
    ) -> List[Dict[str, Any]]:
        async def _do():
            resp = await self._request_google(
                "gmail", "GET", f"users/{user_id}/messages", {"maxResults": max_results, "q": query}
            )
            messages = resp.get("messages", [])
            results = []
            for msg in messages[:5]:
                try:
                    detail = await self._request_google(
                        "gmail", "GET", f"users/{user_id}/messages/{msg['id']}"
                    )
                    results.append(detail)
                except Exception:
                    results.append({"id": msg.get("id", "")})
            return results

        return await self.retry_with_exponential_backoff(_do)

    async def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        async def _do():
            msg_raw = f"To: {to}\nSubject: {subject}\n\n{body}"
            import base64

            body_data = {"raw": base64.urlsafe_b64encode(msg_raw.encode()).decode().rstrip("=")}
            return await self._request_google("gmail", "POST", "users/me/messages/send", body_data)

        return await self.retry_with_exponential_backoff(_do)

    async def read_sheet(
        self, spreadsheet_id: str, range_name: str = "Sheet1!A1:Z100"
    ) -> List[List[Any]]:
        async def _do():
            resp = await self._request_google(
                "sheets", "GET", f"spreadsheets/{spreadsheet_id}/values/{range_name}"
            )
            return resp.get("values", [])

        return await self.retry_with_exponential_backoff(_do)

    async def write_sheet(
        self, spreadsheet_id: str, range_name: str, values: List[List[Any]]
    ) -> Dict[str, Any]:
        async def _do():
            body = {"values": values}
            return await self._request_google(
                "sheets", "POST", f"spreadsheets/{spreadsheet_id}/values/{range_name}:clear", {}
            )

        return await self.retry_with_exponential_backoff(_do)

    async def list_drive_files(
        self, folder_id: Optional[str] = None, max_results: int = 50
    ) -> List[Dict[str, Any]]:
        async def _do():
            q = f"'{folder_id}' in parents" if folder_id else ""
            resp = await self._request_google(
                "drive",
                "GET",
                "files",
                {"q": q, "pageSize": max_results, "fields": "files(id,name,mimeType)"},
            )
            return resp.get("files", [])

        return await self.retry_with_exponential_backoff(_do)

    async def create_calendar_event(
        self,
        calendar_id: str = "primary",
        summary: str = "",
        start_time: str = "",
        end_time: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        async def _do():
            body = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time},
            }
            return await self._request_google(
                "calendar", "POST", f"calendars/{calendar_id}/events", body
            )

        return await self.retry_with_exponential_backoff(_do)

    async def search_youtube(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        async def _do():
            resp = await self._request_google(
                "youtube",
                "GET",
                "search",
                {"part": "snippet", "q": query, "maxResults": max_results, "type": "video"},
            )
            items = resp.get("items", [])
            return [
                {
                    "id": i.get("id", {}).get("videoId", ""),
                    "title": i.get("snippet", {}).get("title", ""),
                    "description": i.get("snippet", {}).get("description", ""),
                }
                for i in items
            ]

        return await self.retry_with_exponential_backoff(_do)
