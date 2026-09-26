extends Node3D
class_name GestureController3D

signal gesture_action(action: String)

var _enabled := false
var _particle_system_3d: GPUParticles3D


func _ready() -> void:
	EventBus.gesture_detected.connect(_on_gesture_detected)
	_particle_system_3d = get_node_or_null("/root/Main/World3D/ParticleWorld/GPUParticles3D")


func _on_gesture_detected(gesture: String, confidence: float, fingers: int) -> void:
	if not _enabled:
		return
	if confidence < 0.6:
		return
	_update_particle_system(gesture)
	match gesture:
		"fist":
			gesture_action.emit("stop")
		"index":
			gesture_action.emit("select")
		"peace":
			gesture_action.emit("confirm")
		"open_hand":
			gesture_action.emit("send")
		"heart":
			gesture_action.emit("feedback_up")
		"swipe":
			gesture_action.emit("clear_chat")
		_:
			gesture_action.emit("unknown")


func _update_particle_system(gesture: String) -> void:
	if not _particle_system_3d:
		return
	var mode := 0
	match gesture:
		"fist":
			mode = 3
		"index":
			mode = 4
		"peace":
			mode = 5
		"open_hand":
			mode = 2
		"swipe":
			mode = 1
		"heart":
			mode = 6
		_:
			mode = 0
	if _particle_system_3d.has_method("set_mode"):
		_particle_system_3d.set_mode(mode)
		if _particle_system_3d.has_method("restart"):
			_particle_system_3d.restart()


func set_enabled(value: bool) -> void:
	_enabled = value
