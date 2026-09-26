"""
AURA YouTube Gesture Control
Control de YouTube mediante gestos de mano con MediaPipe.
Integrado con el backend de AURA para procesamiento y ejecución.

Uso:
    python gesture_control.py
"""

from __future__ import annotations

import os
import sys
import time
import json
import threading
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

import cv2
import mediapipe as mp
import numpy as np

AURA_BACKEND_URL = os.getenv("AURA_BACKEND_URL", "http://localhost:8000")
AURA_API_KEY = os.getenv("AURA_API_KEY", "")
GESTURE_COOLDOWN = 0.3


class GestureDetector:
    def __init__(self) -> None:
        self.mp_hands = mp.solutions.hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.last_gesture: Optional[str] = None
        self.last_gesture_time: float = 0.0
        self.gesture_history: list[str] = []

    def detect_gesture(self, frame: np.ndarray) -> Optional[str]:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.mp_hands.process(rgb)

        if not result.multi_hand_landmarks:
            return None

        for hand_landmarks in result.multi_hand_landmarks:
            landmarks = hand_landmarks.landmark
            gesture = self._classify_gesture(landmarks)
            if gesture:
                return gesture

        return None

    def _classify_gesture(self, landmarks: list) -> Optional[str]:
        finger_tips = [8, 12, 16, 20]
        finger_pips = [6, 10, 14, 18]
        finger_states = []

        for tip, pip in zip(finger_tips, finger_pips):
            tip_y = landmarks[tip].y
            pip_y = landmarks[pip].y
            finger_states.append(tip_y < pip_y)

        thumb_up = landmarks[4].x < landmarks[3].x
        thumb_down = landmarks[4].x > landmarks[3].x

        if all(finger_states):
            return "open_hand"
        if not any(finger_states):
            return "fist"
        if finger_states[0] and not any(finger_states[1:]):
            return "point"
        if finger_states[0] and finger_states[1] and not any(finger_states[2:]):
            return "peace"
        if finger_states[0] and finger_states[1] and finger_states[2] and not finger_states[3]:
            return "three_fingers"
        if all(finger_states) and thumb_down:
            return "five_fingers_down"

        return None

    def can_trigger(self, gesture: str) -> bool:
        now = time.time()
        if gesture == self.last_gesture and now - self.last_gesture_time < GESTURE_COOLDOWN:
            return False
        self.last_gesture = gesture
        self.last_gesture_time = now
        return True


class YouTubeGestureController:
    def __init__(self, backend_url: str = AURA_BACKEND_URL, api_key: str = AURA_API_KEY) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key
        self.headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
        self.detector = GestureDetector()
        self.running = False

    def send_gesture_to_aura(self, gesture: str) -> None:
        payload = {
            "prompt": f"GESTURE_COMMAND:{gesture}",
            "session_id": "youtube-gesture",
            "user_id": "gesture-control",
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.backend_url}/api/chat",
            data=data,
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
        except Exception as exc:
            print(f"[Gesture] Error enviando gesto: {exc}")

    def gesture_to_action(self, gesture: str) -> Optional[str]:
        actions = {
            "open_hand": "play_pause",
            "fist": "mute",
            "point": "forward",
            "peace": "backward",
            "three_fingers": "volume_up",
            "five_fingers_down": "volume_down",
        }
        return actions.get(gesture)

    def run(self) -> None:
        self.running = True
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print("[Gesture] Control de YouTube iniciado. Mostrá gestos a la cámara.")
        print("[Gesture] Gestos: open_hand=play/pause, fist=mute, point=forward, peace=backward, three_fingers=vol+, five=vol-")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue

            gesture = self.detector.detect_gesture(frame)
            if gesture and self.detector.can_trigger(gesture):
                action = self.gesture_to_action(gesture)
                if action:
                    print(f"[Gesture] {gesture} -> {action}")
                    self.send_gesture_to_aura(gesture)

            cv2.putText(frame, f"Gesture: {gesture or 'none'}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("AURA YouTube Gesture Control", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()

    def stop(self) -> None:
        self.running = False


def main() -> int:
    controller = YouTubeGestureController()
    try:
        controller.run()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
