import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # dependencia opcional: opencv-python
    import cv2
except ImportError:  # pragma: no cover - permite que el backend arranque sin opencv
    cv2 = None

import numpy as np
from PIL import Image


@dataclass
class VideoMetadata:
    url: str
    platform: str
    title: str = ""
    description: str = ""
    author: str = ""
    duration_seconds: float = 0.0
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    thumbnail_path: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    resolution: str = ""
    metadata_raw: Dict[str, Any] = field(default_factory=dict)


class SocialCollector:
    SUPPORTED_PLATFORMS = ["youtube", "instagram", "tiktok", "facebook", "x", "twitter"]

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = (
            Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "ARIA_social"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir = self.output_dir / "videos"
        self.audio_dir = self.output_dir / "audio"
        self.thumbnails_dir = self.output_dir / "thumbnails"
        for d in [self.videos_dir, self.audio_dir, self.thumbnails_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self._ydlp_path = self._find_ytdlp()

    def _find_ytdlp(self) -> Optional[str]:
        for cmd in ["yt-dlp", "youtube-dl"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    @property
    def available(self) -> bool:
        return self._ydlp_path is not None

    def detect_platform(self, url: str) -> str:
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        if "instagram.com" in url_lower:
            return "instagram"
        if "tiktok.com" in url_lower:
            return "tiktok"
        if "facebook.com" in url_lower or "fb.watch" in url_lower:
            return "facebook"
        if "x.com" in url_lower or "twitter.com" in url_lower:
            return "x"
        return "unknown"

    def is_supported(self, url: str) -> bool:
        return self.detect_platform(url) in self.SUPPORTED_PLATFORMS

    def collect(self, url: str) -> VideoMetadata:
        platform = self.detect_platform(url)
        if not self.is_supported(url):
            raise ValueError(f"Plataforma no soportada o URL inválida: {url}")
        if not self.available:
            raise RuntimeError("yt-dlp no está instalado. Instalar con: pip install yt-dlp")

        outtmpl = str(self.videos_dir / "%(id)s.%(ext)s")
        cmd = [
            self._ydlp_path,
            "--dump-json",
            "--no-playlist",
            "--flat-playlist",
            "--socket-timeout",
            "30",
            "--no-warnings",
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Error descargando metadata: {result.stderr[-500:]}")

        meta = json.loads(result.stdout.strip().split("\n")[0])

        video_path = self._download_video(url, meta.get("id", "video"))
        audio_path = self._extract_audio(video_path)
        thumbnail_path = self._download_thumbnail(meta)

        return VideoMetadata(
            url=url,
            platform=platform,
            title=meta.get("title", ""),
            description=meta.get("description", ""),
            author=meta.get("uploader", meta.get("channel", "")),
            duration_seconds=meta.get("duration", 0),
            view_count=meta.get("view_count"),
            like_count=meta.get("like_count"),
            comment_count=meta.get("comment_count"),
            thumbnail_path=thumbnail_path,
            video_path=video_path,
            audio_path=audio_path,
            resolution=f"{meta.get('width', 0)}x{meta.get('height', 0)}",
            metadata_raw=meta,
        )

    def collect_batch(self, urls: List[str]) -> List[VideoMetadata]:
        results = []
        for url in urls:
            try:
                result = self.collect(url)
                results.append(result)
            except Exception as e:
                results.append(
                    VideoMetadata(
                        url=url, platform=self.detect_platform(url), metadata_raw={"error": str(e)}
                    )
                )
        return results

    def _download_video(self, url: str, video_id: str) -> str:
        outtmpl = str(self.videos_dir / f"{video_id}.%(ext)s")
        cmd = [
            self._ydlp_path,
            "-o",
            outtmpl,
            "--merge-output-format",
            "mp4",
            "--no-playlist",
            "--socket-timeout",
            "30",
            "--no-warnings",
            url,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
        for f in self.videos_dir.glob(f"{video_id}.*"):
            if f.suffix in (".mp4", ".mov", ".mkv"):
                return str(f)
        raise FileNotFoundError(f"No se encontró video para {video_id}")

    def _extract_audio(self, video_path: str) -> str:
        audio_path = self.audio_dir / f"{Path(video_path).stem}.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(audio_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return str(audio_path)

    def _download_thumbnail(self, meta: Dict[str, Any]) -> Optional[str]:
        thumb_url = meta.get("thumbnail", "")
        if not thumb_url:
            return None
        thumb_path = self.thumbnails_dir / f"{meta.get('id', 'thumb')}.jpg"
        try:
            import urllib.request

            urllib.request.urlretrieve(thumb_url, str(thumb_path))
            return str(thumb_path)
        except Exception:
            return None

    def extract_frames(
        self, video_path: str, fps: float = 1.0, max_frames: int = 50
    ) -> List[Dict[str, Any]]:
        if cv2 is None:
            raise RuntimeError(
                "opencv-python no está instalado; requerido para extraer frames. "
                "Instálalo con: pip install opencv-python"
            )
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = max(1, int(video_fps / fps)) if video_fps > 0 else 1
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames: List[Dict[str, Any]] = []
        frame_idx = 0
        saved = 0
        while cap.isOpened() and saved < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / video_fps if video_fps > 0 else 0
                frame_path = self.thumbnails_dir / f"frame_{saved:05d}.jpg"
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                pil_img.save(str(frame_path), quality=85)
                frames.append(
                    {
                        "index": saved,
                        "timestamp": timestamp,
                        "path": str(frame_path),
                        "width": frame.shape[1],
                        "height": frame.shape[0],
                    }
                )
                saved += 1
            frame_idx += 1
        cap.release()
        return frames

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        if cv2 is None:
            return {}
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {}
        info = {
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration": (
                cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                if cap.get(cv2.CAP_PROP_FPS) > 0
                else 0
            ),
        }
        cap.release()
        return info
