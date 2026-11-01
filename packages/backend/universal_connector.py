# Universal connector: GitHub, Drive, Files - centralized, fail-closed
from __future__ import annotations
from typing import Any, Dict
from .git_integrator import git_integrator
from .drive_connector import drive_connector
from .io_universal import universal_io


class UniversalConnector:
    def __init__(self) -> None:
        pass

    def github_clone(self, url: str, dest: str) -> Dict[str, Any]:
        return git_integrator.clone(url, dest)

    def drive_list_instagram(self, folder_name: str = "instagram") -> Dict[str, Any]:
        return drive_connector.list_in_folder(folder_name)

    def read_local(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        return universal_io.list(path, recursive)


universal_connector = UniversalConnector()
