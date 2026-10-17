# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger('ARIA.SocialVideo')

try:
    from backend.services.vision_engine import VisionEngine
except Exception:
    VisionEngine = None

@dataclass
class VideoFrameAnalysis:
    t: float
    description: str
    model: str

@dataclass
class VideoStreamAnalysis:
    url: str
    platform: str
    duration_estimate: Optional[float]
    fps_sample: float
    frames_analyzed: int
    timeline: List[VideoFrameAnalysis]
    visual_summary: str
    audio_summary: Optional[str]
    key_moments: List[str]
    transcript_hint: Optional[str]
    overall_summary: str
    ts: str

def _guess_platform(url: str) -> str:
    u = url.lower()
    if 'instagram.com' in u: return 'instagram'
    if 'tiktok.com' in u: return 'tiktok'
    if 'youtube.com' in u or 'youtu.be' in u: return 'youtube'
    if 'x.com' in u or 'twitter.com' in u: return 'x'
    if 'facebook.com' in u or 'fb.watch' in u: return 'facebook'
    if 'linkedin.com' in u: return 'linkedin'
    if 'threads.net' in u: return 'threads'
    if 'bsky.app' in u: return 'bluesky'
    if 'reddit.com' in u: return 'reddit'
    if 'pinterest.com' in u: return 'pinterest'
    return 'generic'

class SocialVideoStreamAnalyzer:
    def __init__(self, vision: Optional[VisionEngine] = None):
        self.vision = vision or (VisionEngine() if VisionEngine else None)

    async def analyze_from_frames(
        self,
        url: str,
        frames_b64: List[Dict[str, Any]],
        audio_transcript: Optional[str] = None,
        fps_sample: float = 0.5,
        on_progress: Optional[Callable[[int,int], None]] = None,
    ) -> VideoStreamAnalysis:
        platform = _guess_platform(url)
        timeline: List[VideoFrameAnalysis] = []
        total = len(frames_b64)
        for i, f in enumerate(frames_b64):
            t = float(f.get('t') or 0.0)
            img_b64 = f.get('image_b64') or ''
            if not img_b64:
                continue
            try:
                res = self.vision.analyze_frame(img_b64, session_id=f'social_{platform}') if self.vision else {}
            except Exception:
                res = {'description': '', 'model': 'error'}
            timeline.append(VideoFrameAnalysis(t=t, description=res.get('description') or '', model=res.get('model') or 'vision'))
            if on_progress:
                try: on_progress(i+1, total)
                except Exception: pass
            await asyncio.sleep(0)
        key_moments = self._key_moments(timeline)
        vis_sum = self._vis_sum(timeline)
        overall = self._overall(vis_sum, audio_transcript, key_moments)
        return VideoStreamAnalysis(
            url=url,
            platform=platform,
            duration_estimate=(timeline[-1].t if timeline else None),
            fps_sample=fps_sample,
            frames_analyzed=len(timeline),
            timeline=timeline,
            visual_summary=vis_sum,
            audio_summary=(audio_transcript[:280] + '…' if audio_transcript and len(audio_transcript)>280 else audio_transcript) if audio_transcript else None,
            key_moments=key_moments,
            transcript_hint=(audio_transcript[:500] if audio_transcript else None),
            overall_summary=overall,
            ts=datetime.utcnow().isoformat() + 'Z',
        )

    def _key_moments(self, tl: List[VideoFrameAnalysis]) -> List[str]:
        if len(tl) < 2: return [m.description for m in tl if m.description]
        out: List[str] = []
        step = max(1, len(tl)//6)
        for m in tl[::step][:6]:
            d = (m.description or '').strip()
            if d and len(d)>8: out.append(f'{m.t:.1f}s: {d[:120]}')
        return out

    def _vis_sum(self, tl: List[VideoFrameAnalysis]) -> str:
        if not tl: return 'Sin fotogramas analizados.'
        d = [m.description for m in tl if m.description]
        if not d: return 'Video renderizado detectado, sin descripción visual clara.'
        b = ' '.join(d)
        return (b[:400] + '…') if len(b)>400 else b

    def _overall(self, vis: str, tr: Optional[str], km: List[str]) -> str:
        p: List[str] = []
        p.append('**Análisis visual (frames renderizados, sin descarga):**')
        p.append(vis)
        if tr:
            p.append('\n**Audio/transcripción (contexto):**')
            p.append(tr[:350] + ('…' if len(tr)>350 else ''))
        if km:
            p.append('\n**Momentos clave:**')
            for k in km: p.append(f'- {k}')
        p.append('\n_Método: viewport-frame-sampling (renderizado). No se descarga MP4._')
        return '\n'.join(p)

social_video_analyzer = SocialVideoStreamAnalyzer()
