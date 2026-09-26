"""Spatial gesture engine for AURA - Module 24.

Procesamiento de eventos gestuales en tiempo real (pinch, throw, claw,
clap, explode) para manipular widgets y modelos 3D en interfaz transparente.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class GestureType(str, Enum):
    PINCH = "pinch"
    THROW = "throw"
    CLAW = "claw"
    CLAP = "clap"
    EXPLODE = "explode"


class Hand(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


@dataclass
class SpatialCoordinate:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    world_x: float = 0.0
    world_y: float = 0.0
    world_z: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "world_x": self.world_x,
            "world_y": self.world_y,
            "world_z": self.world_z,
        }


@dataclass
class GestureFrame:
    frame_id: str
    gesture_type: str
    hand: str
    coordinates: List[SpatialCoordinate]
    confidence: float = 1.0
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def centroid(self) -> Dict[str, float]:
        if not self.coordinates:
            return {"x": 0.0, "y": 0.0, "z": 0.0}
        n = len(self.coordinates)
        return {
            "x": round(sum(c.x for c in self.coordinates) / n, 4),
            "y": round(sum(c.y for c in self.coordinates) / n, 4),
            "z": round(sum(c.z for c in self.coordinates) / n, 4),
        }


class HandTrackingEngine:
    """Procesa y registra eventos gestuales en tiempo real."""

    def __init__(self, max_history: int = 500) -> None:
        self.gestures: List[Dict[str, Any]] = []
        self.max_history = max_history
        self._prev_centroid: Optional[Dict[str, float]] = None

    def process_frame(self, frame: GestureFrame) -> Dict[str, Any]:
        return self._interpret(frame)

    def process_gesture(
        self,
        gesture_type: str,
        hand: str = "right",
        coordinates: Optional[List[Dict[str, float]]] = None,
        confidence: float = 1.0,
        duration_ms: float = 0.0,
    ) -> Dict[str, Any]:
        coords = [SpatialCoordinate(**c) for c in (coordinates or [{"x": 0, "y": 0, "z": 0}])]
        frame = GestureFrame(
            frame_id=f"gest-{int(time.time() * 1000000)}-{len(self.gestures)}",
            gesture_type=gesture_type,
            hand=hand,
            coordinates=coords,
            confidence=confidence,
            duration_ms=duration_ms,
        )
        return self._interpret(frame)

    def _interpret(self, frame: GestureFrame) -> Dict[str, Any]:
        centroid = frame.centroid()
        velocity = self._compute_velocity(centroid)
        self._prev_centroid = centroid

        result: Dict[str, Any] = {
            "frame_id": frame.frame_id,
            "gesture_type": frame.gesture_type,
            "hand": frame.hand,
            "coordinates": [c.to_dict() for c in frame.coordinates],
            "centroid": centroid,
            "velocity": velocity,
            "confidence": frame.confidence,
            "timestamp": frame.timestamp,
            "duration_ms": frame.duration_ms,
            "action": self._map_action(frame.gesture_type, centroid, velocity),
        }
        self.gestures.append(result)
        if len(self.gestures) > self.max_history:
            self.gestures = self.gestures[-self.max_history :]
        return result

    def _compute_velocity(self, centroid: Dict[str, float]) -> Dict[str, float]:
        if self._prev_centroid is None:
            return {"x": 0.0, "y": 0.0, "z": 0.0}
        return {
            "x": round(centroid["x"] - self._prev_centroid["x"], 4),
            "y": round(centroid["y"] - self._prev_centroid["y"], 4),
            "z": round(centroid["z"] - self._prev_centroid["z"], 4),
        }

    @staticmethod
    def _map_action(gesture_type: str, centroid: Dict[str, float], velocity: Dict[str, float]) -> Dict[str, Any]:
        actions: Dict[str, Dict[str, Any]] = {
            GestureType.PINCH.value: {"type": "select", "target": "widget", "coordinate": centroid},
            GestureType.THROW.value: {"type": "move", "target": "model", "velocity": velocity},
            GestureType.CLAW.value: {"type": "grab", "target": "canvas"},
            GestureType.CLAP.value: {"type": "toggle", "target": "overlay"},
            GestureType.EXPLODE.value: {"type": "reset", "target": "scene"},
        }
        return actions.get(gesture_type, {"type": "noop", "target": "none", "gesture": gesture_type})

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.gestures[-limit:]


@dataclass
class CanvasWidget:
    id: str
    type: str
    position: Dict[str, float]
    visible: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class CanvasModel:
    id: str
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    rotation: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    scale: float = 1.0


class SpatialCanvas:
    """Administra widgets y modelos 3D en la interfaz espacial transparente."""

    def __init__(self) -> None:
        self.widgets: Dict[str, CanvasWidget] = {}
        self.models: Dict[str, CanvasModel] = {}
        self.transform_log: List[Dict[str, Any]] = []
        self._max_log = 500

    def process_gesture(self, frame: GestureFrame) -> Dict[str, Any]:
        gesture_type = frame.gesture_type
        centroid = frame.centroid()

        actions: Dict[str, Any] = {
            GestureType.PINCH.value: self._action_pinch(centroid),
            GestureType.THROW.value: self._action_throw(centroid, frame),
            GestureType.CLAW.value: self._action_claw(),
            GestureType.CLAP.value: self._action_clap(),
            GestureType.EXPLODE.value: self._action_explode(),
        }
        result = actions.get(
            gesture_type,
            {"action": "noop", "gesture_type": gesture_type, "centroid": centroid},
        )
        result["gesture_type"] = gesture_type
        result["hand"] = frame.hand
        result["timestamp"] = frame.timestamp
        return result

    def add_widget(self, widget_type: str = "generic", position: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        widget_id = f"widget-{int(time.time() * 1000000)}"
        widget = CanvasWidget(
            id=widget_id,
            type=widget_type,
            position=position or {"x": 0.0, "y": 0.0, "z": 0.0},
        )
        self.widgets[widget_id] = widget
        return {
            "status": "created",
            "widget": {
                "id": widget_id,
                "type": widget.type,
                "position": widget.position,
                "visible": widget.visible,
                "created_at": widget.created_at,
            },
        }

    def remove_widget(self, widget_id: str) -> Dict[str, Any]:
        if widget_id not in self.widgets:
            return {"status": "not_found", "widget_id": widget_id}
        del self.widgets[widget_id]
        return {"status": "removed", "widget_id": widget_id}

    def move_widget(self, widget_id: str, coordinate: SpatialCoordinate) -> Dict[str, Any]:
        widget = self.widgets.get(widget_id)
        if not widget:
            return {"status": "not_found", "widget_id": widget_id}
        widget.position = {"x": coordinate.x, "y": coordinate.y, "z": coordinate.z}
        return {"status": "moved", "widget_id": widget_id, "position": widget.position}

    def transform_model(self, model_id: str, transform: Dict[str, Any]) -> Dict[str, Any]:
        model = self.models.get(model_id)
        if not model:
            model = CanvasModel(id=model_id)
            self.models[model_id] = model
        if "position" in transform:
            model.position = transform["position"]
        if "rotation" in transform:
            model.rotation = transform["rotation"]
        if "scale" in transform:
            model.scale = float(transform["scale"])

        entry: Dict[str, Any] = {
            "model_id": model_id,
            "transform": transform,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.transform_log.append(entry)
        if len(self.transform_log) > self._max_log:
            self.transform_log = self.transform_log[-self._max_log :]

        return {
            "status": "transformed",
            "model_id": model_id,
            "position": model.position,
            "rotation": model.rotation,
            "scale": model.scale,
        }

    def get_state(self) -> Dict[str, Any]:
        return {
            "widgets": [
                {"id": w.id, "type": w.type, "position": w.position, "visible": w.visible, "created_at": w.created_at}
                for w in self.widgets.values()
            ],
            "models": [
                {"id": m.id, "position": m.position, "rotation": m.rotation, "scale": m.scale}
                for m in self.models.values()
            ],
            "widget_count": len(self.widgets),
            "model_count": len(self.models),
            "recent_transforms": self.transform_log[-20:],
        }

    def _action_pinch(self, centroid: Dict[str, float]) -> Dict[str, Any]:
        widget_id = min(self.widgets, key=lambda w: self._distance(w.position, centroid)) if self.widgets else None
        return {
            "action": "select",
            "target": "widget",
            "widget_id": widget_id,
            "coordinate": centroid,
        }

    def _action_throw(self, centroid: Dict[str, float], frame: GestureFrame) -> Dict[str, Any]:
        model_id = min(self.models, key=lambda m: self._distance(m.position, centroid)) if self.models else None
        velocity = frame.centroid()
        return {
            "action": "move",
            "target": "model",
            "model_id": model_id,
            "direction": velocity,
        }

    def _action_claw(self) -> Dict[str, Any]:
        return {"action": "grab", "target": "canvas"}

    def _action_clap(self) -> Dict[str, Any]:
        for widget in self.widgets.values():
            widget.visible = not widget.visible
        return {"action": "toggle_visibility", "target": "widgets", "widgets_affected": len(self.widgets)}

    def _action_explode(self) -> Dict[str, Any]:
        self.widgets.clear()
        self.models.clear()
        self.transform_log.clear()
        return {"action": "reset", "target": "scene", "widgets_cleared": True, "models_cleared": True}

    @staticmethod
    def _distance(pos_a: Dict[str, float], pos_b: Dict[str, float]) -> float:
        return sum((pos_a.get(k, 0.0) - pos_b.get(k, 0.0)) ** 2 for k in ("x", "y", "z")) ** 0.5
