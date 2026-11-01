# Google Drive connector (service-account first, OAuth2 fallback, fail-closed)
from __future__ import annotations
import os, json
from pathlib import Path
from typing import Any, Dict, Optional
try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from google_auth_oauthlib.flow import InstalledAppFlow
except Exception:
    build = None; Credentials = None; service_account = None; InstalledAppFlow = None
SCOPES = ['https://www.googleapis.com/auth/drive']

class DriveConnector:
    def __init__(self, creds_path: Optional[str]=None, token_path: Optional[str]=None) -> None:
        self.creds_path = creds_path or os.getenv("GOOGLE_CREDS_PATH") or str(Path(__file__).parent.parent / "credentials" / "service-account-key.json")
        self.token_path = token_path or os.getenv("GOOGLE_TOKEN_PATH") or "token.json"
        self.service = None
        self._connect()

    def _connect_service_account(self) -> "Optional[service_account.Credentials]":
        if service_account is None: return None
        try:
            if isinstance(self.creds_path, str):
                with open(self.creds_path) as f: data = json.load(f)
                if data.get("type") == "service_account":
                    return service_account.Credentials.from_service_account_info(data, scopes=SCOPES)
            return None
        except Exception:
            return None

    def _connect(self) -> None:
        if build is None: return
        creds = None
        sa_creds = self._connect_service_account()
        if sa_creds:
            try:
                from google.auth.transport.requests import Request
                sa_creds.refresh(Request())
                creds = sa_creds
            except Exception as e:
                creds = None
        else:
            try:
                if self.token_path and os.path.exists(self.token_path) and Credentials is not None:
                    creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception: creds = None
            if not creds and self.creds_path and InstalledAppFlow is not None:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                    if self.token_path:
                        with open(self.token_path,"w",encoding="utf-8") as f2:
                            f2.write(creds.to_json())
                except Exception: creds = None
        try:
            if creds and getattr(creds,"valid",False):
                self.service = build("drive","v3",credentials=creds)
        except Exception: self.service = None
    def is_ready(self) -> bool: return self.service is not None
    def list_files(self, q: Optional[str]=None, page_size: int=20) -> Dict[str,Any]:
        if not self.service: return {"status":"not_ready","files":[]}
        try:
            res = self.service.files().list(q=q, pageSize=page_size, fields='files(id,name,mimeType,parents,webViewLink)').execute()
            return {"status":"ok","files":res.get("files",[])}
        except Exception as e: return {"status":"error","error":str(e),"files":[]}
    def find_folder(self, name: str) -> Dict[str,Any]:
        if not name: return {"status":"invalid","folder":None}
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        out = self.list_files(q=q,page_size=10)
        files = out.get("files") or []
        return {"status":out.get("status"),"folder": files[0] if files else None}
    def list_in_folder(self, folder_name: str="instagram", page_size: int=50) -> Dict[str,Any]:
        f = self.find_folder(folder_name)
        folder = f.get("folder")
        if not folder: return {"status":"folder_not_found","folder_name":folder_name,"files":[]}
        q = f"'{folder['id']}' in parents and trashed=false"
        out = self.list_files(q=q,page_size=page_size)
        return {"status":out.get("status"),"folder_name":folder_name,"folder_id":folder["id"],"files":out.get("files",[])}
drive_connector = DriveConnector()

def get_drive_connector() -> "DriveConnector":
    global drive_connector
    if not drive_connector.is_ready():
        drive_connector = DriveConnector()
    return drive_connector
