"""AURA Vision ROI — dynamic filters inside hand-defined polygon.

Usage:
    from vision_roi import VisionROI
    roi = VisionROI()
    roi.start()
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple


class VisionROI:
    def __init__(self) -> None:
        self.running = False
        self.filter_index = 0
        self.filters = ["none", "cyan", "thermal", "ascii", "dots", "pixelate", "edge"]
        self.current_filter = "none"
        self.polygon_points: List[Tuple[int, int]] = []
        self._thread: Optional[threading.Thread] = None
        self._gesture_callbacks: List[Any] = []
        self._filter_callbacks: List[Any] = []

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

    def next_filter(self) -> None:
        self.filter_index = (self.filter_index + 1) % len(self.filters)
        self.current_filter = self.filters[self.filter_index]
        self._notify_filter_change()

    def prev_filter(self) -> None:
        self.filter_index = (self.filter_index - 1) % len(self.filters)
        self.current_filter = self.filters[self.filter_index]
        self._notify_filter_change()

    def set_filter(self, name: str) -> None:
        if name in self.filters:
            self.filter_index = self.filters.index(name)
            self.current_filter = name
            self._notify_filter_change()

    def _notify_filter_change(self) -> None:
        for cb in self._filter_callbacks:
            try:
                cb(self.current_filter)
            except Exception:
                pass

    def _loop(self) -> None:
        try:
            import cv2
            import mediapipe as mp
            import numpy as np
        except ImportError:
            return
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            model_complexity=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        while self.running:
            ret, frame = cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = mp_hands.process(rgb)
            pts = []
            if result.multi_hand_landmarks:
                hand = result.multi_hand_landmarks[0].landmark
                tips = [4, 8, 12, 16, 20]
                h, w = frame.shape[:2]
                pts = [(int(hand[i].x * w), int(hand[i].y * h)) for i in tips]
                if len(pts) >= 4:
                    self.polygon_points = pts[:4]
                    roi = self._extract_roi(frame, pts[:4])
                    if roi is not None and roi.size > 0:
                        filtered = self._apply_filter(roi, self.current_filter)
                        frame = self._paste_roi(frame, filtered, pts[:4])
            for cb in self._gesture_callbacks:
                try:
                    cb(self.current_filter, pts)
                except Exception:
                    pass
        cap.release()

    def _extract_roi(self, frame, pts: List[Tuple[int, int]]) -> Optional[Any]:
        try:
            import numpy as np
            h, w = frame.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            pts_np = np.array(pts, dtype=np.int32)
            cv2.fillConvexPoly(mask, pts_np, 255)
            roi = cv2.bitwise_and(frame, frame, mask=mask)
            x, y, w_box, h_box = cv2.boundingRect(pts_np)
            if w_box <= 0 or h_box <= 0:
                return None
            return roi[y:y + h_box, x:x + w_box]
        except Exception:
            return None

    def _apply_filter(self, roi, filter_name: str) -> Any:
        try:
            import cv2
            import numpy as np
            if filter_name == "none":
                return roi
            if filter_name == "cyan":
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                hsv[:, :, 0] = (hsv[:, :, 0] + 90) % 180
                hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(int) * 1.2, 0, 255).astype(np.uint8)
                return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            if filter_name == "thermal":
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                return cv2.applyColorMap(gray, cv2.COLORMAP_JET)
            if filter_name == "ascii":
                return self._ascii_filter(roi)
            if filter_name == "dots":
                return self._dots_filter(roi)
            if filter_name == "pixelate":
                return self._pixelate_filter(roi)
            if filter_name == "edge":
                return self._edge_filter(roi)
        except Exception:
            pass
        return roi

    def _ascii_filter(self, roi) -> Any:
        try:
            import cv2
            import numpy as np
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (40, 20), interpolation=cv2.INTER_AREA)
            chars = " .:-=+*#%@"
            ascii_art = []
            for row in small:
                line = "".join(chars[max(0, min(len(chars) - 1, int(p / 255 * (len(chars) - 1))))] for p in row)
                ascii_art.append(line)
            text_img = np.zeros((roi.shape[0], roi.shape[1], 3), dtype=np.uint8)
            y_offset = 10
            for line in ascii_art:
                cv2.putText(text_img, line, (5, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
                y_offset += 12
            return text_img
        except Exception:
            return roi

    def _dots_filter(self, roi) -> Any:
        try:
            import cv2
            import numpy as np
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            dots = np.zeros_like(roi)
            step = 6
            for y in range(0, roi.shape[0], step):
                for x in range(0, roi.shape[1], step):
                    intensity = gray[y, x] if y < gray.shape[0] and x < gray.shape[1] else 0
                    radius = max(1, int(intensity / 255 * 3))
                    color = (0, int(255 - intensity), int(intensity))
                    cv2.circle(dots, (x, y), radius, color, -1)
            return dots
        except Exception:
            return roi

    def _pixelate_filter(self, roi) -> Any:
        try:
            import cv2
            import numpy as np
            h, w = roi.shape[:2]
            pixel_size = 8
            small = cv2.resize(roi, (w // pixel_size, h // pixel_size), interpolation=cv2.INTER_LINEAR)
            return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        except Exception:
            return roi

    def _edge_filter(self, roi) -> Any:
        try:
            import cv2
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        except Exception:
            return roi

    def _paste_roi(self, frame, roi, pts: List[Tuple[int, int]]) -> Any:
        try:
            import numpy as np
            pts_np = np.array(pts, dtype=np.int32)
            x, y, w_box, h_box = cv2.boundingRect(pts_np)
            if w_box <= 0 or h_box <= 0:
                return frame
            roi_resized = cv2.resize(roi, (w_box, h_box), interpolation=cv2.INTER_AREA)
            if roi_resized.shape[:2] != (h_box, w_box):
                return frame
            mask = np.zeros((h_box, w_box), dtype=np.uint8)
            cv2.fillConvexPoly(mask, np.array(pts, dtype=np.int32) - np.array([x, y]), 255)
            for c in range(3):
                frame[y:y + h_box, x:x + w_box, c] = np.where(mask > 0, roi_resized[:, :, c], frame[y:y + h_box, x:x + w_box, c])
        except Exception:
            pass
        return frame

    def add_gesture_callback(self, cb) -> None:
        self._gesture_callbacks.append(cb)

    def add_filter_callback(self, cb) -> None:
        self._filter_callbacks.append(cb)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "filter": self.current_filter,
            "filters_available": self.filters,
            "polygon_points": len(self.polygon_points),
        }
