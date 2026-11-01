from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from github import Github, GithubException


class GitHubClient:
    def __init__(self) -> None:
        token = os.environ.get("GITHUB_TOKEN")
        self._gh = Github(token) if token else Github()
        self._token = bool(token)

    def list_repos(self, user: Optional[str] = None, per_page: int = 50) -> Dict[str, Any]:
        try:
            if user:
                u = self._gh.get_user(user)
                repos = u.get_repos()
            else:
                u = self._gh.get_user()
                repos = u.get_repos()
            out = []
            for r in repos[:per_page]:
                out.append({
                    "name": r.name,
                    "full_name": r.full_name,
                    "description": r.description,
                    "html_url": r.html_url,
                    "clone_url": r.clone_url,
                    "language": r.language,
                    "stars": r.stargazers_count,
                    "forks": r.forks_count,
                    "private": r.private,
                    "updated_at": str(r.updated_at),
                    "default_branch": r.default_branch,
                })
            return {"status": "ok", "repos": out, "count": len(out), "authenticated": self._token}
        except GithubException as exc:
            return {"error": str(exc)}

    def search_repos(self, query: str, per_page: int = 30) -> Dict[str, Any]:
        try:
            result = self._gh.search_repositories(query)
            out = []
            for r in result[:per_page]:
                out.append({
                    "name": r.name,
                    "full_name": r.full_name,
                    "description": r.description,
                    "html_url": r.html_url,
                    "language": r.language,
                    "stars": r.stargazers_count,
                    "forks": r.forks_count,
                    "updated_at": str(r.updated_at),
                })
            return {"status": "ok", "query": query, "repos": out, "count": result.totalCount}
        except GithubException as exc:
            return {"error": str(exc)}

    def get_repo(self, full_name: str) -> Dict[str, Any]:
        try:
            r = self._gh.get_repo(full_name)
            return {
                "status": "ok",
                "name": r.name,
                "full_name": r.full_name,
                "description": r.description,
                "html_url": r.html_url,
                "clone_url": r.clone_url,
                "language": r.language,
                "stars": r.stargazers_count,
                "forks": r.forks_count,
                "open_issues": r.open_issues_count,
                "default_branch": r.default_branch,
                "topics": r.get_topics(),
                "license": r.license.spdx_id if r.license else None,
            }
        except GithubException as exc:
            return {"error": str(exc)}

    def file_content(self, full_name: str, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
        try:
            r = self._gh.get_repo(full_name)
            content = r.get_contents(path, ref=ref)
            if isinstance(content, list):
                return {"error": "path es un directorio, usa list_dir"}
            return {
                "status": "ok",
                "path": content.path,
                "size": content.size,
                "encoding": content.encoding,
                "content": content.decoded_content.decode("utf-8", errors="replace"),
                "sha": content.sha,
            }
        except GithubException as exc:
            return {"error": str(exc)}

    def list_dir(self, full_name: str, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
        try:
            r = self._gh.get_repo(full_name)
            contents = r.get_contents(path, ref=ref)
            out = []
            for c in contents:
                out.append({
                    "name": c.name,
                    "path": c.path,
                    "type": c.type,
                    "size": c.size,
                    "html_url": c.html_url,
                })
            return {"status": "ok", "path": path, "items": out, "count": len(out)}
        except GithubException as exc:
            return {"error": str(exc)}

    def issues(self, full_name: str, state: str = "open", per_page: int = 30) -> Dict[str, Any]:
        try:
            r = self._gh.get_repo(full_name)
            out = []
            for i in r.get_issues(state=state)[:per_page]:
                out.append({
                    "number": i.number,
                    "title": i.title,
                    "state": i.state,
                    "html_url": i.html_url,
                    "created_at": str(i.created_at),
                    "labels": [l.name for l in i.labels],
                })
            return {"status": "ok", "repo": full_name, "state": state, "issues": out}
        except GithubException as exc:
            return {"error": str(exc)}


_gh: GitHubClient | None = None


def _get_gh() -> GitHubClient:
    global _gh
    if _gh is None:
        _gh = GitHubClient()
    return _gh


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")

    if action == "list_repos":
        return _list_repos(params)
    if action == "search_repos":
        return _search_repos(params)
    if action == "get_repo":
        return _get_repo(params)
    if action == "file_content":
        return _file_content(params)
    if action == "list_dir":
        return _list_dir(params)
    if action == "issues":
        return _issues(params)
    if action == "auth":
        return _auth(params)
    return {"error": f"accion desconocida: {action}"}


def _list_repos(params: Dict[str, Any]) -> Dict[str, Any]:
    return _get_gh().list_repos(user=params.get("user"), per_page=int(params.get("per_page", 50)))


def _search_repos(params: Dict[str, Any]) -> Dict[str, Any]:
    query = params.get("query", "")
    if not query:
        return {"error": "query requerido"}
    return _get_gh().search_repos(query, per_page=int(params.get("per_page", 30)))


def _get_repo(params: Dict[str, Any]) -> Dict[str, Any]:
    full = params.get("full_name", "")
    if not full:
        return {"error": "full_name requerido (ej: usuario/repo)"}
    return _get_gh().get_repo(full)


def _file_content(params: Dict[str, Any]) -> Dict[str, Any]:
    full = params.get("full_name", "")
    path = params.get("path", "")
    if not full or not path:
        return {"error": "full_name y path requeridos"}
    return _get_gh().file_content(full, path, params.get("ref"))


def _list_dir(params: Dict[str, Any]) -> Dict[str, Any]:
    full = params.get("full_name", "")
    path = params.get("path", "")
    if not full:
        return {"error": "full_name requerido"}
    return _get_gh().list_dir(full, path, params.get("ref"))


def _issues(params: Dict[str, Any]) -> Dict[str, Any]:
    full = params.get("full_name", "")
    if not full:
        return {"error": "full_name requerido"}
    return _get_gh().issues(full, state=params.get("state", "open"))


def _auth(params: Dict[str, Any]) -> Dict[str, Any]:
    return {"authenticated": bool(_get_gh()._token), "provider": "github"}
