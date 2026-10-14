from __future__ import annotations

import json
import mimetypes
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request, error

import yaml


class MemoryType(str, Enum):
    FACT = "fact"
    DECISION = "decision"
    INSIGHT = "insight"
    PATTERN = "pattern"
    PROCEDURE = "procedure"
    REFERENCE = "reference"


class MemorySource(str, Enum):
    USER_CHAT = "user_chat"
    INSTAGRAM_ANALYSIS = "instagram_analysis"
    WEB_SEARCH = "web_search"
    CODE_ANALYSIS = "code_analysis"
    DRIVE_SCAN = "drive_scan"
    MODEL_BENCHMARK = "model_benchmark"
    SYSTEM_OBSERVATION = "system_observation"


@dataclass
class MemoryNote:
    type: str = "memory"
    subtype: MemoryType = MemoryType.FACT
    source: MemorySource = MemorySource.USER_CHAT
    confidence: float = 0.8
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    content: str = ""
    title: str = ""

    def to_markdown(self) -> str:
        frontmatter = {
            "type": self.type,
            "subtype": self.subtype.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "tags": self.tags,
            "links": self.links,
            "created": self.created,
            "updated": self.updated,
        }
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
        return f"---\n{fm_yaml}\n---\n\n# {self.title}\n\n{self.content}"


@dataclass
class CanvasNode:
    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    text: str = ""
    file: str = ""
    label: str = ""
    color: str = ""


@dataclass
class CanvasEdge:
    id: str
    from_node: str
    to_node: str
    label: str = ""


@dataclass
class Canvas:
    nodes: List[CanvasNode] = field(default_factory=list)
    edges: List[CanvasEdge] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "x": n.x,
                    "y": n.y,
                    "width": n.width,
                    "height": n.height,
                    **({"text": n.text} if n.text else {}),
                    **({"file": n.file} if n.file else {}),
                    **({"label": n.label} if n.label else {}),
                    **({"color": n.color} if n.color else {}),
                }
                for n in self.nodes
            ],
            "edges": [
                {"id": e.id, "from": e.from_node, "to": e.to_node, "label": e.label}
                for e in self.edges
            ],
        }


class RenderAPIError(Exception):
    pass


class RenderAPIClient:
    def __init__(self, base_url: str = "http://localhost:27123", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode() if data else None

        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode())
        except error.HTTPError as e:
            raise RenderAPIError(f"HTTP {e.code}: {e.read().decode()}")
        except error.URLError as e:
            raise RenderAPIError(f"Connection failed: {e}")

    def health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def dataview_query(self, query: str) -> Dict[str, Any]:
        return self._request("POST", "/api/dataview/query", {"query": query})

    def dataview_js(self, script: str) -> Dict[str, Any]:
        return self._request("POST", "/api/dataview/js", {"script": script})

    def vault_read(self, path: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/vault/read?path={request.quote(path)}")

    def vault_write(self, path: str, content: str) -> Dict[str, Any]:
        return self._request("POST", "/api/vault/write", {"path": path, "content": content})

    def vault_list(self, path: str = "") -> Dict[str, Any]:
        return self._request("GET", f"/api/vault/list?path={request.quote(path)}")

    def vault_delete(self, path: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/api/vault/delete?path={request.quote(path)}")

    def tasks_query(self, query: str) -> Dict[str, Any]:
        return self._request("POST", "/api/tasks/query", {"query": query})


class ObsidianBridge:
    def __init__(
        self,
        vault_path: str,
        render_api_url: str = "http://localhost:27123",
        memory_folder: str = "memory",
        drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
    ):
        self.vault_path = vault_path
        self.memory_folder = memory_folder
        self.client = RenderAPIClient(render_api_url)
        self.drive_sync = DriveSync(drive_folder_id=drive_folder_id)

    def write_memory_note(self, note: MemoryNote) -> str:
        safe_title = "".join(c for c in note.title if c.isalnum() or c in " -_").strip()
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{safe_title or 'note'}.md"
        rel_path = os.path.join(self.memory_folder, filename)
        full_path = os.path.join(self.vault_path, rel_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(note.to_markdown())

        return rel_path

    def write_memory_note_via_api(self, note: MemoryNote) -> Dict[str, Any]:
        safe_title = "".join(c for c in note.title if c.isalnum() or c in " -_").strip()
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{safe_title or 'note'}.md"
        rel_path = os.path.join(self.memory_folder, filename)

        return self.client.vault_write(rel_path, note.to_markdown())

    def read_note(self, rel_path: str) -> str:
        full_path = os.path.join(self.vault_path, rel_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_note_via_api(self, rel_path: str) -> Dict[str, Any]:
        return self.client.vault_read(rel_path)

    def query_dataview(self, dql: str) -> Dict[str, Any]:
        return self.client.dataview_query(dql)

    def query_dataview_js(self, script: str) -> Dict[str, Any]:
        return self.client.dataview_js(script)

    def search_memory(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        source: Optional[MemorySource] = None,
        subtype: Optional[MemoryType] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        conditions = ['type = "memory"']
        if query:
            conditions.append(f'contains(file.name, "{query}")')
        if tags:
            tag_cond = " OR ".join([f'contains(tags, "{t}")' for t in tags])
            conditions.append(f"({tag_cond})")
        if source:
            conditions.append(f'source = "{source.value}"')
        if subtype:
            conditions.append(f'subtype = "{subtype.value}"')

        where_clause = " AND ".join(conditions)
        dql = f"TABLE file.name, subtype, source, confidence, tags, links, created FROM \"{self.memory_folder}\" WHERE {where_clause} SORT created DESC LIMIT {limit}"

        result = self.client.dataview_query(dql)
        return result.get("values", []) if isinstance(result, dict) else []

    def create_canvas(
        self,
        nodes: List[CanvasNode],
        edges: List[CanvasEdge],
        filename: str,
    ) -> str:
        canvas = Canvas(nodes=nodes, edges=edges)
        rel_path = os.path.join("canvas", f"{filename}.canvas")
        full_path = os.path.join(self.vault_path, rel_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(canvas.to_json(), f, ensure_ascii=False, indent=2)

        return rel_path

    def create_canvas_via_api(
        self,
        nodes: List[CanvasNode],
        edges: List[CanvasEdge],
        filename: str,
    ) -> Dict[str, Any]:
        canvas = Canvas(nodes=nodes, edges=edges)
        rel_path = os.path.join("canvas", f"{filename}.canvas")
        content = json.dumps(canvas.to_json(), ensure_ascii=False, indent=2)
        return self.client.vault_write(rel_path, content)

    def generate_memory_canvas(
        self,
        center_topic: str,
        related_notes: List[Dict[str, Any]],
        filename: str,
    ) -> str:
        center_id = str(uuid.uuid4())
        center_node = CanvasNode(
            id=center_id,
            type="text",
            x=0,
            y=0,
            width=300,
            height=100,
            text=f"# {center_topic}",
            color="#4a90d9",
        )

        nodes = [center_node]
        edges = []

        for i, note in enumerate(related_notes):
            angle = (i / len(related_notes)) * 2 * 3.14159
            radius = 400
            import math
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)

            note_id = str(uuid.uuid4())
            title = note.get("file.name", "Untitled")
            subtype = note.get("subtype", "fact")
            color_map = {
                "fact": "#2ecc71",
                "decision": "#e74c3c",
                "insight": "#f39c12",
                "pattern": "#9b59b6",
            }
            node = CanvasNode(
                id=note_id,
                type="file",
                x=x,
                y=y,
                width=250,
                height=80,
                file=note.get("file.path", ""),
                label=title,
                color=color_map.get(subtype, "#95a5a6"),
            )
            nodes.append(node)

            edges.append(CanvasEdge(
                id=str(uuid.uuid4()),
                from_node=center_id,
                to_node=note_id,
                label=subtype,
            ))

        return self.create_canvas(nodes, edges, filename)

    def health_check(self) -> bool:
        try:
            result = self.client.health()
            return result.get("status") == "ok"
        except Exception:
            return False

    def drive_health_check(self) -> bool:
        return self.drive_sync.is_ready()

    def sync_to_drive(self, folders: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sync vault folders to Google Drive.
        
        NOTE: Service account cannot upload to personal Drive (no storage quota).
        For full sync, configure Drive Bridge plugin in Obsidian with OAuth user credentials.
        This method only works if using a Shared Drive with service account access.
        """
        if folders is None:
            folders = ["memory", "canvas"]

        results = {"total_uploaded": 0, "total_updated": 0, "total_errors": 0, "by_folder": {}}

        for folder in folders:
            local_path = os.path.join(self.vault_path, folder)
            if not os.path.exists(local_path):
                results["by_folder"][folder] = {"status": "skipped", "reason": "not found"}
                continue

            res = self.drive_sync.sync_vault_folder(local_path)
            results["by_folder"][folder] = res
            results["total_uploaded"] += res.get("uploaded", 0)
            results["total_updated"] += res.get("updated", 0)
            results["total_errors"] += res.get("errors", 0)

        return results

    def upload_to_drive(self, local_path: str, drive_name: Optional[str] = None) -> Dict[str, Any]:
        """Upload a single file to Drive."""
        full_path = local_path if os.path.isabs(local_path) else os.path.join(self.vault_path, local_path)
        return self.drive_sync.upload_file(full_path, drive_name)

    def list_drive_files(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in the Drive folder."""
        return self.drive_sync.list_files(parent_id)


class DriveSyncError(Exception):
    pass


class DriveSync:
    """Sync vault files to Google Drive using service account API."""

    def __init__(
        self,
        drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
        creds_path: Optional[str] = None,
    ):
        self.drive_folder_id = drive_folder_id
        self.creds_path = creds_path or os.getenv(
            "GOOGLE_CREDS_PATH",
            str(Path(__file__).parent.parent.parent.parent / "credentials" / "service-account-key.json")
        )
        self._service = None
        self._connect()

    def _connect(self) -> None:
        try:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
        except ImportError:
            raise DriveSyncError("google-api-python-client not installed")

        if not os.path.exists(self.creds_path):
            raise DriveSyncError(f"Service account key not found: {self.creds_path}")

        with open(self.creds_path) as f:
            data = json.load(f)

        if data.get("type") != "service_account":
            raise DriveSyncError("Credentials file is not a service account")

        SCOPES = ["https://www.googleapis.com/auth/drive"]
        creds = service_account.Credentials.from_service_account_info(data, scopes=SCOPES)

        from google.auth.transport.requests import Request
        creds.refresh(Request())

        self._service = build("drive", "v3", credentials=creds)

    def is_ready(self) -> bool:
        return self._service is not None

    def _mime_type(self, path: str) -> str:
        mime, _ = mimetypes.guess_type(path)
        return mime or "application/octet-stream"

    def upload_file(self, local_path: str, drive_name: Optional[str] = None, parent_id: Optional[str] = None) -> Dict[str, Any]:
        if not self._service:
            raise DriveSyncError("Drive service not initialized")

        name = drive_name or os.path.basename(local_path)
        parent = parent_id or self.drive_folder_id

        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(local_path, mimetype=self._mime_type(local_path), resumable=True)

        file_metadata = {"name": name, "parents": [parent]}
        file = self._service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,name,webViewLink,mimeType,size"
        ).execute()

        return {
            "status": "uploaded",
            "id": file.get("id"),
            "name": file.get("name"),
            "webViewLink": file.get("webViewLink"),
            "mimeType": file.get("mimeType"),
            "size": file.get("size"),
        }

    def update_file(self, drive_file_id: str, local_path: str) -> Dict[str, Any]:
        if not self._service:
            raise DriveSyncError("Drive service not initialized")

        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(local_path, mimetype=self._mime_type(local_path), resumable=True)

        file = self._service.files().update(
            fileId=drive_file_id,
            media_body=media,
            fields="id,name,webViewLink,mimeType,size"
        ).execute()

        return {
            "status": "updated",
            "id": file.get("id"),
            "name": file.get("name"),
            "webViewLink": file.get("webViewLink"),
            "mimeType": file.get("mimeType"),
            "size": file.get("size"),
        }

    def find_file(self, name: str, parent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self._service:
            raise DriveSyncError("Drive service not initialized")

        parent = parent_id or self.drive_folder_id
        q = f"name='{name}' and '{parent}' in parents and trashed=false"
        res = self._service.files().list(q=q, fields="files(id,name,mimeType,size,webViewLink)").execute()
        files = res.get("files", [])
        return files[0] if files else None

    def list_files(self, parent_id: Optional[str] = None, page_size: int = 100) -> List[Dict[str, Any]]:
        if not self._service:
            raise DriveSyncError("Drive service not initialized")

        parent = parent_id or self.drive_folder_id
        q = f"'{parent}' in parents and trashed=false"
        res = self._service.files().list(
            q=q,
            pageSize=page_size,
            fields="files(id,name,mimeType,size,webViewLink,modifiedTime)"
        ).execute()
        return res.get("files", [])

    def delete_file(self, drive_file_id: str) -> bool:
        if not self._service:
            raise DriveSyncError("Drive service not initialized")

        try:
            self._service.files().delete(fileId=drive_file_id).execute()
            return True
        except Exception:
            return False

    def sync_vault_folder(self, local_folder: str, drive_parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Sync a local folder to Drive recursively."""
        if not os.path.exists(local_folder):
            return {"status": "error", "error": f"Local folder not found: {local_folder}"}

        results = {"uploaded": 0, "updated": 0, "errors": 0, "details": []}
        parent = drive_parent_id or self.drive_folder_id

        for root, dirs, files in os.walk(local_folder):
            for file in files:
                if file.startswith(".") or file.endswith(".tmp"):
                    continue

                local_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_path, local_folder)
                drive_name = rel_path.replace(os.sep, "/")

                existing = self.find_file(drive_name, parent)
                try:
                    if existing:
                        res = self.update_file(existing["id"], local_path)
                        results["updated"] += 1
                    else:
                        res = self.upload_file(local_path, drive_name, parent)
                        results["uploaded"] += 1
                    results["details"].append({"file": drive_name, "action": res["status"], "id": res["id"]})
                except Exception as e:
                    results["errors"] += 1
                    results["details"].append({"file": drive_name, "action": "error", "error": str(e)})

        return results


def create_bridge(
    vault_path: str,
    render_api_url: str = "http://localhost:27123",
    memory_folder: str = "memory",
    drive_folder_id: str = "1pA6egurq1NuAXQYiU4JaSm5u02MjPxp0",
) -> ObsidianBridge:
    return ObsidianBridge(vault_path, render_api_url, memory_folder, drive_folder_id)