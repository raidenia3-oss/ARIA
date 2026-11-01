"""
Rutas API REST para conectar Aria con Google Drive.

Endpoints:
- GET  /api/drive/status         — Estado de conexión de Drive
- POST /api/drive/connect        — Inicia el flow OAuth2 y guarda token
- GET  /api/drive/list-files     — Lista archivos en Drive
- GET  /api/drive/find-folder    — Busca una carpeta por nombre
- GET  /api/drive/list-in-folder — Lista archivos dentro de una carpeta
- GET  /api/drive/download       — Descarga un archivo por ID
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.drive_connector import drive_connector, DriveConnector

router = APIRouter(prefix="/api/drive", tags=["google-drive"])


class ConnectRequest(BaseModel):
    creds_path: Optional[str] = Field(None, description="Path al client_secret.json")
    token_path: Optional[str] = Field(None, description="Path donde guardar el token.json")


class ListFilesRequest(BaseModel):
    query: Optional[str] = Field(None, description="Consulta de búsqueda de Drive (Q parameter)")
    page_size: int = Field(20, ge=1, le=100)


class FindFolderRequest(BaseModel):
    name: str = Field(..., description="Nombre de la carpeta a buscar")


class ListInFolderRequest(BaseModel):
    folder_name: str = Field(..., description="Nombre de la carpeta")
    page_size: int = Field(50, ge=1, le=100)


class DownloadRequest(BaseModel):
    file_id: str = Field(..., description="ID del archivo en Google Drive")
    output_path: Optional[str] = Field(None, description="Path local donde guardar el archivo")


@router.get("/status")
async def drive_status() -> Dict[str, Any]:
    """Verifica si Aria está conectada a tu Google Drive."""
    return {
        "connected": drive_connector.is_ready(),
        "creds_path": drive_connector.creds_path,
        "token_path": drive_connector.token_path,
        "service": "google-drive-v3",
    }


@router.post("/connect")
async def connect_drive(payload: ConnectRequest) -> Dict[str, Any]:
    """Inicia el proceso de conexión OAuth2 con Google Drive.

    Si proporcionas `creds_path`, usa ese client_secret.json.
    Si no, usa GOOGLE_CREDS_PATH del entorno.
    El token se guarda en token_path (o GOOGLE_TOKEN_PATH, o token.json).
    """
    import os

    creds_path = payload.creds_path or os.getenv("GOOGLE_CREDS_PATH")
    token_path = payload.token_path or os.getenv("GOOGLE_TOKEN_PATH") or "token.json"

    if not creds_path or not os.path.exists(creds_path):
        return {
            "connected": False,
            "error": "No se encontró client_secret.json. Configure GOOGLE_CREDS_PATH o pase creds_path.",
            "instructions": _drive_setup_instructions(),
        }

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        global drive_connector
        drive_connector = DriveConnector(creds_path=creds_path, token_path=token_path)

        return {
            "connected": drive_connector.is_ready(),
            "token_path": token_path,
            "message": "Conexión exitosa. Se guardó el token OAuth2." if drive_connector.is_ready() else "Error de conexión.",
        }
    except Exception as exc:
        return {
            "connected": False,
            "error": str(exc),
            "instructions": _drive_setup_instructions(),
        }


@router.get("/list-files")
async def list_files(query: Optional[str] = None, page_size: int = 20) -> Dict[str, Any]:
    """Lista archivos en Google Drive."""
    if not drive_connector.is_ready():
        raise HTTPException(status_code=403, detail="Drive no conectado. POST /api/drive/connect primero.")
    return drive_connector.list_files(q=query, page_size=page_size)


@router.get("/find-folder/{name}")
async def find_folder(name: str) -> Dict[str, Any]:
    """Busca una carpeta por nombre en Google Drive."""
    if not drive_connector.is_ready():
        raise HTTPException(status_code=403, detail="Drive no conectado. POST /api/drive/connect primero.")
    return drive_connector.find_folder(name)


@router.get("/list-in-folder/{folder_name}")
async def list_in_folder(folder_name: str, page_size: int = 50) -> Dict[str, Any]:
    """Lista archivos dentro de una carpeta de Drive."""
    if not drive_connector.is_ready():
        raise HTTPException(status_code=403, detail="Drive no conectado. POST /api/drive/connect primero.")
    return drive_connector.list_in_folder(folder_name=folder_name, page_size=page_size)


@router.get("/download/{file_id}")
async def download_file(file_id: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """Descarga un archivo de Google Drive por su ID."""
    if not drive_connector.is_ready():
        raise HTTPException(status_code=403, detail="Drive no conectado. POST /api/drive/connect primero.")

    try:
        import io
        from googleapiclient.http import MediaIoBaseDownload

        request = drive_connector.service.files().get(fileId=file_id, fields="name,mimeType")
        metadata = request.execute()
        file_name = metadata.get("name", f"file_{file_id}")
        mime_type = metadata.get("mimeType", "application/octet-stream")

        if not output_path:
            output_path = os.getenv("AURA_DOWNLOAD_DIR", "downloads")
        output = Path(output_path)
        output.mkdir(parents=True, exist_ok=True)
        out_file = output / file_name

        req = drive_connector.service.files().get_media(fileId=file_id)
        fh = io.FileIO(str(out_file), "wb")
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()

        return {
            "status": "downloaded",
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "path": str(out_file),
            "size_bytes": out_file.stat().st_size,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _drive_setup_instructions() -> str:
    return (
        "1. Ve a Google Cloud Console → APIs & Services → Credentials\n"
        "2. Crea una OAuth 2.0 Client ID (tipo 'Desktop app')\n"
        "3. Descarga client_secret.json\n"
        "4. Activa la API de Google Drive\n"
        "5. POST /api/drive/connect con {\"creds_path\": \"/ruta/client_secret.json\"}\n"
        "6. Haz clic en el enlace que aparece para autorizar a Aria\n"
        "7. El token se guarda automáticamente en token.json"
    )


from pathlib import Path


