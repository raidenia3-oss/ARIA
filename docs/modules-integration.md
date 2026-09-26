# AURA — Modules Integration Guide

## Voice Assistant (JARVIS-style)

Tab: **Voice**

Features:
- Wake-word detection: `hey aura`
- Speech-to-text: converts voice to commands
- Command execution: system status, campaign summary, email summary
- Text-to-speech: speaks responses back
- Executive summary: synthesized briefings

Usage:
1. Go to Voice tab
2. Click **Start Listening**
3. Say `hey aura, estado del sistema`
4. AURA responds with spoken summary

Dependencies:
- `SpeechRecognition`
- `pyttsx3`
- `pyaudio` (for microphone access)

## Gesture Recognition + Overlays

Tab: **Gestures**

Features:
- Real-time hand tracking via MediaPipe
- Finger counting and gesture classification
- Meme/emoji overlay on camera feed
- Callbacks for gesture events

Supported gestures:
- `open_hand` — 4+ fingers
- `fist` — 0 fingers
- `index` — 1 finger
- `peace` — 2 fingers
- `swipe` — unknown gesture

Usage:
1. Go to Gestures tab
2. Click **Start Camera**
3. Show hand to camera
4. Toggle overlay with **Toggle Overlay**

Dependencies:
- `opencv-python`
- `mediapipe`

## Vision ROI — Dynamic Filters

Tab: **Vision**

Features:
- Hand-defined polygon ROI (4 fingertips)
- Real-time filters inside the ROI:
  - `none` — original
  - `cyan` — cyan shift
  - `thermal` — thermal vision
  - `ascii` — ASCII style (placeholder)
  - `dots` — dot matrix (placeholder)
- Cycle filters with **Next Filter**

Usage:
1. Go to Vision tab
2. Click **Start Camera**
3. Show 4 fingers to define polygon
4. Click **Next Filter** to cycle effects

Dependencies:
- `opencv-python`
- `mediapipe`
- `numpy`

## OSINT Dashboard

Tab: **OSINT**

Features:
- Categorized tool directory
- Quick search links
- Synthetic identity generator
- Local mode (no external dependencies)

Categories:
- `people` — username search, Google Dorks, image search
- `search` — Shodan, Censys, VirusTotal, Wayback
- `darknet` — Ahmia, Torch
- `maps` — Google Maps, Bing Maps, Waze

Usage:
1. Go to OSINT tab
2. Select category
3. Click **Load Tools** to see directory
4. Click **Generate Identity** for synthetic profiles

## Integration in aura_app.py

All modules are imported as tabs in the desktop app:

```python
from voice_engine import VoiceEngine
from gesture_engine import GestureEngine
from vision_roi import VisionROI
from osint_dashboard import OSINTDashboard
```

Each module runs in its own thread and communicates with the UI via callbacks and queues.

## Next Steps

1. Install missing dependencies: `pip install opencv-python mediapipe SpeechRecognition pyttsx3 pyaudio`
2. Run `aura_app.py`
3. Open each tab and test the modules
4. Configure API keys in `.env` for real AI providers

## Notes

- Camera modules require webcam access
- Voice module requires microphone access
- All modules work in embedded mode (no HTTP required)
- For production, add error handling and permission dialogs
