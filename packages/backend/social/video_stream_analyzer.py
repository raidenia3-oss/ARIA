# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
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
    ocr_text: Optional[str] = None
    objects: List[str] = None
    scene_type: Optional[str] = None
    action: Optional[str] = None
    confidence: Optional[float] = None

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
    transcript_full: Optional[str]
    entities: List[str]
    actions: List[str]
    scenes: List[str]
    ocr_all: List[str]
    overall_summary: str
    comprehension_level: str
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

def _clean(txt: str) -> str:
    if not txt: return ''
    return ' '.join(txt.replace('\n',' ').replace('\r',' ').split())

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
            if not img_b64: continue
            try:
                res = self.vision.analyze_frame(img_b64, session_id=f'social_{platform}') if self.vision else {}
            except Exception:
                res = {'description': '', 'model': 'error'}
            desc = _clean(res.get('description') or '')
            timeline.append(VideoFrameAnalysis(
                t=t,
                description=desc,
                model=res.get('model') or 'vision',
                ocr_text=None,
                objects=[],
                scene_type=None,
                action=None,
                confidence=None,
            ))
            if on_progress:
                try: on_progress(i+1,total)
                except Exception: pass
            await asyncio.sleep(0)
        key_moments = self._key_moments(timeline)
        vis_sum = self._vis_sum(timeline)
        entities = self._entities(timeline)
        actions = self._actions(timeline)
        scenes = self._scenes(timeline)
        ocr_all = self._ocr_all(timeline)
        tr_full = _clean(audio_transcript) if audio_transcript else None
        overall = self._overall(vis_sum, tr_full, key_moments, entities, actions, scenes, ocr_all)
        return VideoStreamAnalysis(
            url=url,
            platform=platform,
            duration_estimate=(timeline[-1].t if timeline else None),
            fps_sample=fps_sample,
            frames_analyzed=len(timeline),
            timeline=timeline,
            visual_summary=vis_sum,
            audio_summary=(tr_full[:320]+'…' if tr_full and len(tr_full)>320 else tr_full) if tr_full else None,
            key_moments=key_moments,
            transcript_hint=(tr_full[:600] if tr_full else None),
            transcript_full=tr_full,
            entities=entities,
            actions=actions,
            scenes=scenes,
            ocr_all=ocr_all,
            overall_summary=overall,
            comprehension_level=self._compr(entities,actions,scenes,tr_full,timeline),
            ts=datetime.utcnow().isoformat() + 'Z',
        )

    def _key_moments(self, tl: List[VideoFrameAnalysis]) -> List[str]:
        if len(tl)<2: return [m.description for m in tl if m.description][:5]
        out=[]; step=max(1,len(tl)//8)
        for m in tl[::step][:8]:
            d=(m.description or '').strip()
            if d and len(d)>10: out.append(f'{m.t:.1f}s: {d[:140]}')
        return out

    def _vis_sum(self, tl: List[VideoFrameAnalysis]) -> str:
        if not tl: return 'Sin fotogramas analizados.'
        d=[m.description for m in tl if m.description]
        if not d: return 'Video renderizado detectado, sin descripción visual detallada.'
        b=' '.join(d)
        return (b[:600]+'…') if len(b)>600 else b

    def _entities(self, tl: List[VideoFrameAnalysis]) -> List[str]:
        seen=set(); out=[]
        for m in tl:
            txt=m.description or ''
            for w in ['persona','hombre','mujer','niño','objeto','texto','logo','producto','animal']:
                if w in txt.lower() and w not in seen: seen.add(w); out.append(w)
        return out[:15]

    def _actions(self, tl: List[VideoFrameAnalysis]) -> List[str]:
        seen=set(); out=[]
        verbs=['habla','camina','mira','sonríe','mueve','toca','abre','cierra','escribe','muestra','baila','come']
        for m in tl:
            t=m.description.lower()
            for v in verbs:
                if v in t and v not in seen: seen.add(v); out.append(v)
        return out[:12]

    def _scenes(self, tl: List[VideoFrameAnalysis]) -> List[str]:
        seen=set(); out=[]
        tags=['interior','exterior','calle','cocina','oficina','habitación','fondo','paisaje']
        for m in tl:
            t=m.description.lower()
            for g in tags:
                if g in t and g not in seen: seen.add(g); out.append(g)
        return out[:10]

    def _ocr_all(self, tl: List[VideoFrameAnalysis]) -> List[str]:
        return []

    def _compr(self, entities, actions, scenes, tr_full, tl):
        score=0
        if tr_full: score+=2
        if len(tl)>=3: score+=1
        if entities: score+=1
        if actions: score+=1
        if scenes: score+=1
        if score>=5: return 'alta'
        if score>=3: return 'media'
        return 'básica'

    def _overall(self, vis, tr_full, km, entities, actions, scenes, ocr_all):
        p=[]
        p.append('**Comprensión visual (frames renderizados, SIN descarga MP4):**')
        p.append(vis)
        if tr_full:
            p.append('\n**Audio/diálogo (transcripción):**')
            p.append(tr_full[:500]+('…' if len(tr_full)>500 else ''))
        if km:
            p.append('\n**Momentos clave (cronología):**')
            for k in km: p.append(f'- {k}')
        if entities or actions or scenes:
            p.append('\n**Contexto semántico:**')
            if entities: p.append(f'- Entidades: {", ".join(entities)}')
            if actions: p.append(f'- Acciones: {", ".join(actions)}')
            if scenes: p.append(f'- Escenas: {", ".join(scenes)}')
        p.append('\n_Método: viewport-frame-sampling (renderizado). Sin descarga de archivo MP4. Fusión tiempo+visión._')
        return '\n'.join(p)

social_video_analyzer = SocialVideoStreamAnalyzer()
