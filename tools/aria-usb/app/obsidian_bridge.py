from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
    ):
        self.vault_path = vault_path
        self.memory_folder = memory_folder
        self.client = RenderAPIClient(render_api_url)

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


def create_bridge(
    vault_path: str,
    render_api_url: str = "http://localhost:27123",
    memory_folder: str = "memory",
) -> ObsidianBridge:
    return ObsidianBridge(vault_path, render_api_url, memory_folder)