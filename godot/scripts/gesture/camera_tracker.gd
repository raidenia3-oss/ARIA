extends Node
class_name CameraTracker

signal gesture_detected(gesture: String, confidence: float, fingers: int)

var _enabled := false
var _http: HTTPClient
var _timer: Timer
var _connected := false


func _ready() -> void:
	_http = HTTPClient.new()
	_timer = Timer.new()
	_timer.wait_time = 0.1
	_timer.timeout.connect(_poll_stream)
	add_child(_timer)
	EventBus.gesture_detected.connect(_on_gesture_from_bus)


func set_enabled(value: bool) -> void:
	_enabled = value
	if _enabled:
		_connected = false
		_timer.start()
	else:
		_timer.stop()
		if _http:
			_http.close()
			_connected = false


func _poll_stream() -> void:
	if not _enabled or not _http:
		return
	var status := _http.get_status()
	if status == HTTPClient.STATUS_CONNECTED or status == HTTPClient.STATUS_BODY:
		var err := _http.poll()
		if err != OK:
			return
		while _http.get_status() == HTTPClient.STATUS_BODY:
			var chunk := _http.read_response_body_chunk()
			if chunk.is_empty():
				break
			_parse_sse(chunk.get_string_from_utf8())
		return
	if not _connected:
		var err := _http.connect_to_url("http://localhost:8000/api/gesture/stream")
		if err == OK:
			_http.poll()
			var req := _http.request(HTTPClient.METHOD_GET, "/api/gesture/stream", [])
			_connected = true


func _parse_sse(data: String) -> void:
	var lines := data.split("\n")
	for line in lines:
		line = line.strip_edges()
		if line.begins_with("data:"):
			var payload := line.substr(5).strip_edges()
			var parsed := JSON.parse_string(payload)
			if not parsed or not parsed is Dictionary:
				continue
			var gesture := str(parsed.get("gesture", "unknown"))
			var confidence := float(parsed.get("confidence", 0.0))
			var fingers := int(parsed.get("fingers", 0))
			if gesture != "unknown" and confidence > 0.6:
				gesture_detected.emit(gesture, confidence, fingers)


func _on_gesture_from_bus(gesture: String, confidence: float, fingers: int) -> void:
	if _enabled:
		gesture_detected.emit(gesture, confidence, fingers)
