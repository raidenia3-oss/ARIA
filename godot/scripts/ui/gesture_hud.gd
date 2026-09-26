extends Control
class_name GestureHUD

signal gesture_action(action: String)

@onready var gesture_label: Label = $GestureLabel
@onready var confidence_bar: ProgressBar = $ConfidenceBar
@onready var fingers_label: Label = $FingersLabel
@onready var status_indicator: ColorRect = $StatusIndicator
@onready var hand_sprite: Sprite2D = $HandSprite

var _enabled := false
var _current_gesture := "unknown"
var _target_confidence := 0.0
var _current_confidence := 0.0
var _timer: Timer


func _ready() -> void:
	_timer = Timer.new()
	_timer.wait_time = 0.05
	_timer.timeout.connect(_update_hud)
	add_child(_timer)
	EventBus.gesture_detected.connect(_on_gesture_detected)
	_configure_nodes()


func _configure_nodes() -> void:
	if gesture_label:
		gesture_label.text = "Gesto: --"
	if confidence_bar:
		confidence_bar.min_value = 0.0
		confidence_bar.max_value = 1.0
		confidence_bar.value = 0.0
	if fingers_label:
		fingers_label.text = "Dedos: 0"
	if status_indicator:
		status_indicator.color = Color(0.3, 0.3, 0.3)


func set_enabled(value: bool) -> void:
	_enabled = value
	if status_indicator:
		status_indicator.color = Color(0.2, 0.8, 0.2) if value else Color(0.3, 0.3, 0.3)
	if value:
		_timer.start()
	else:
		_timer.stop()
		if gesture_label:
			gesture_label.text = "Gesto: --"
		if confidence_bar:
			confidence_bar.value = 0.0
		if fingers_label:
			fingers_label.text = "Dedos: 0"


func _on_gesture_detected(gesture: String, confidence: float, fingers: int) -> void:
	if not _enabled:
		return
	_current_gesture = gesture
	_target_confidence = confidence
	if fingers_label:
		fingers_label.text = "Dedos: %d" % fingers
	_emit_action(gesture)


func _update_hud() -> void:
	if not _enabled:
		return
	_current_confidence = lerp(_current_confidence, _target_confidence, 0.2)
	var color := Color(1.0, 1.0, 1.0)
	if confidence_bar:
		confidence_bar.value = _current_confidence
	if gesture_label:
		match _current_gesture:
			"fist":
				color = Color(1.0, 0.3, 0.3)
			"index":
				color = Color(0.3, 1.0, 0.3)
			"peace":
				color = Color(0.3, 0.8, 1.0)
			"open_hand":
				color = Color(1.0, 1.0, 0.3)
			"swipe":
				color = Color(1.0, 0.5, 1.0)
			"unknown":
				color = Color(0.5, 0.5, 0.5)
		gesture_label.text = "Gesto: %s" % _current_gesture
		gesture_label.modulate = color
	if hand_sprite:
		hand_sprite.modulate = color


func _emit_action(gesture: String) -> void:
	match gesture:
		"fist":
			gesture_action.emit("stop")
		"index":
			gesture_action.emit("select")
		"peace":
			gesture_action.emit("confirm")
		"open_hand":
			gesture_action.emit("send")
		"swipe":
			gesture_action.emit("clear_chat")
		"heart":
			gesture_action.emit("feedback_up")
		_:
			gesture_action.emit("unknown")
