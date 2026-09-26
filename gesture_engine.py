"""AURA Gesture Engine — MediaPipe hand tracking + overlay/meme triggers.

Usage:
    from gesture_engine import GestureEngine
    engine = GestureEngine()
    engine.start()
"""

from __future__ import annotations

import collections
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class GestureEngine:
    def __init__(self) -> None:
        self.running = False
        self.camera_index = 0
        self.overlay_mode = True
        self.gesture: str = "none"
        self.confidence: float = 0.0
        self.finger_count: int = 0
        self.hand_landmarks: Any = None
        self.hand_center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.state: str = "idle"
        self.combo: List[str] = []
        self.last_gesture_time: float = 0.0
        self.combo_window: float = 1.2
        self._thread: Optional[threading.Thread] = None
        self._frame_callbacks: List[Any] = []
        self._gesture_callbacks: List[Any] = []
        self.meme_catalog: Dict[str, str] = {
            "open_hand": "✋",
            "fist": "✊",
            "index": "☝️",
            "peace": "✌️",
            "heart": "❤️",
            "swipe": "👋",
            "rock": "🤘",
            "ok": "👌",
        }
        self.gesture_actions: Dict[str, str] = {
            "fist": "Stop/Kill",
            "index": "Select/Point",
            "peace": "Confirm/Yes",
            "open_hand": "Start/All",
            "heart": "Favorite/Like",
            "swipe": "Swipe/Next",
            "rock": "Action/Custom",
            "ok": "OK/Accept",
        }

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)

    def _loop(self) -> None:
        try:
            import cv2
            import mediapipe as mp
        except ImportError:
            return
        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            model_complexity=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        mp_draw = mp.solutions.drawing_utils
        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = mp_hands.process(rgb)
            gesture, confidence, fingers = "none", 0.0, 0
            if result.multi_hand_landmarks:
                self.hand_landmarks = result.multi_hand_landmarks[0]
                mp_draw.draw_landmarks(frame, self.hand_landmarks, mp.solutions.hands.HAND_CONNECTIONS)
                lm = self.hand_landmarks.landmark
                cx = sum(p.x for p in lm) / len(lm)
                cy = sum(p.y for p in lm) / len(lm)
                cz = sum(p.z for p in lm) / len(lm)
                self.hand_center = (cx, cy, cz)
                gesture, confidence, fingers = self._classify(result)
            now = time.time()
            if gesture != "none" and gesture != self.gesture:
                if now - self.last_gesture_time < self.combo_window:
                    self.combo.append(gesture)
                else:
                    self.combo = [gesture]
                self.last_gesture_time = now
                if len(self.combo) >= 3:
                    combo_name = " -> ".join(self.combo[-3:])
                    self.state = f"combo:{combo_name}"
                    self.combo = []
                else:
                    self.state = "active"
            elif gesture == "none":
                if now - self.last_gesture_time > self.combo_window and self.state != "idle":
                    self.state = "idle"
                    self.combo = []
            self.gesture = gesture
            self.confidence = confidence
            self.finger_count = fingers
            if self.overlay_mode:
                frame = self._draw_overlay(frame, gesture, confidence, fingers)
            for cb in self._frame_callbacks:
                try:
                    cb(frame, gesture, confidence)
                except Exception:
                    pass
            if gesture != "none":
                for cb in self._gesture_callbacks:
                    try:
                        cb(gesture, confidence, fingers)
                    except Exception:
                        pass
        cap.release()

    def _classify(self, result) -> Tuple[str, float, int]:
        if not result.multi_hand_landmarks:
            return "none", 0.0, 0
        lm = result.multi_hand_landmarks[0].landmark
        fingers = self._count_fingers(lm)
        self.finger_count = fingers

        # Rock: índice y meñique extendidos, medio y anular bajados
        index_up = lm[8].y < lm[6].y
        middle_down = lm[12].y > lm[10].y
        ring_down = lm[16].y > lm[14].y
        pinky_up = lm[20].y < lm[18].y
        if index_up and middle_down and ring_down and pinky_up:
            return "rock", 0.9, fingers

        # Heart: índice y meñique extendidos, medio y anular flexados hacia centro
        if index_up and pinky_up and middle_down and ring_down:
            # Verificar separación de índice y meñique (forma corazón)
            distance_index_pinky = abs(lm[8].x - lm[20].x)
            middle_distance = abs(lm[9].x - lm[13].x)
            if middle_distance < 0.1 and distance_index_pinky > 0.1:
                return "heart", 0.88, fingers
            return "rock", 0.8, fingers

        # Swipe: detectar movimiento horizontal de la mano entre frames
        if fingers <= 2 and self.hand_center and self.hand_center[0] != 0.0:
            cx = sum(p.x for p in lm) / len(lm)
            prev_cx = self.hand_center[0]
            if abs(cx - prev_cx) > 0.25:
                return "swipe", 0.6, fingers

        if fingers == 0:
            return "fist", 0.9, fingers
        if fingers == 1:
            return "index", 0.9, fingers
        if fingers == 2:
            return "peace", 0.9, fingers
        if fingers == 3:
            return "ok", 0.8, fingers
        if fingers == 4:
            return "open_hand", 0.9, fingers
        if fingers == 5:
            return "open_hand", 0.95, fingers
        return "swipe", 0.5, fingers

    def _count_fingers(self, lm) -> int:
        fingers = 0
        if lm[8].y < lm[6].y:
            fingers += 1
        if lm[12].y < lm[10].y:
            fingers += 1
        if lm[16].y < lm[14].y:
            fingers += 1
        if lm[20].y < lm[18].y:
            fingers += 1
        thumb_extended = abs(lm[4].x - lm[3].x) > 0.05
        if thumb_extended:
            fingers += 1
        return fingers

    def _draw_overlay(self, frame, gesture: str, confidence: float, fingers: int) -> Any:
        try:
            import cv2
            meme = self.meme_catalog.get(gesture, "❓")
            action = self.gesture_actions.get(gesture, "Unknown")
            cv2.rectangle(frame, (10, 10), (400, 110), (31, 41, 51), -1)
            cv2.rectangle(frame, (10, 10), (400, 110), (102, 252, 241), 2)
            cv2.putText(frame, f"Gesture: {gesture}", (25, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, f"Emoji: {meme}  Action: {action}", (25, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (197, 198, 199), 2)
            cv2.putText(frame, f"Fingers: {fingers}  Conf: {confidence:.2f}", (25, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (139, 141, 143), 1)
            if gesture != "none":
                cv2.putText(frame, f"{meme}", (500, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (102, 252, 241), 3)
        except Exception:
            pass
        return frame

    def add_frame_callback(self, cb) -> None:
        self._frame_callbacks.append(cb)

    def add_gesture_callback(self, cb) -> None:
        self._gesture_callbacks.append(cb)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "gesture": self.gesture,
            "confidence": self.confidence,
            "fingers": self.finger_count,
            "overlay_mode": self.overlay_mode,
            "camera": self.camera_index,
            "state": self.state,
            "combo": self.combo,
        }

    def get_available_gestures(self) -> List[str]:
        return list(self.meme_catalog.keys())

    def set_camera(self, index: int) -> None:
        self.camera_index = index
