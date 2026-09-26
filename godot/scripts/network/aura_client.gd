extends Node
class_name AuraClient

signal message_sent(prompt: String)
signal stream_token(token: String, done: bool)
signal connected()
signal disconnected()
signal media_sent(media_type: String)

const DEFAULT_LOCAL_URL := "http://localhost:8000"
const DEFAULT_CLOUD_URL := "http://localhost:8000"
var _http: HTTPClient
var _ws: WebSocketPeer
var _connected: bool = false
var _last_prompt := ""
var _poll_wifi_timer: Timer
var _poll_earthquake_timer: Timer
var _health_timer: Timer
var _reconnect_timer: Timer
var _busy := false
var _backend_url := DEFAULT_LOCAL_URL
var _cloud_url := DEFAULT_CLOUD_URL
var _use_local := true
var _reconnect_attempts := 0
var _max_reconnect_attempts := 3


func _ready() -> void:
	_http = HTTPClient.new()
	_ws = WebSocketPeer.new()

	_poll_wifi_timer = Timer.new()
	_poll_wifi_timer.wait_time = 1.0
	_poll_wifi_timer.timeout.connect(_request_wifi)
	add_child(_poll_wifi_timer)

	_poll_earthquake_timer = Timer.new()
	_poll_earthquake_timer.wait_time = 5.0
	_poll_earthquake_timer.timeout.connect(_request_earthquakes)
	add_child(_poll_earthquake_timer)

	_health_timer = Timer.new()
	_health_timer.wait_time = 10.0
	_health_timer.timeout.connect(_check_connection)
	add_child(_health_timer)

	_reconnect_timer = Timer.new()
	_reconnect_timer.wait_time = 5.0
	_reconnect_timer.timeout.connect(_attempt_reconnect)
	add_child(_reconnect_timer)

	_discover_backend()
	_health_timer.start()


func _discover_backend() -> void:
	var cloud_urls := []
	if _cloud_url != "":
		cloud_urls.append(_cloud_url)

	var candidate_urls := ["http://localhost:8000", "http://127.0.0.1:8000"] + cloud_urls

	for url in candidate_urls:
		if _probe_backend(url):
			_backend_url = url
			_use_local = url.begins_with("http://localhost") or url.begins_with("http://127.0.0.1")
			print("[AuraClient] Backend discovered: %s (local=%s)" % [_backend_url, _use_local])
			_connect_http(_backend_url)
			_register_with_orchestrator(_backend_url)
			return

	push_error("No AURA backend found")
	disconnected.emit()


func _register_with_orchestrator(url: String) -> void:
	var registration := {
		"node_id": "godot-client",
		"node_type": "pc",
		"base_url": url,
		"role": "light",
		"capabilities": ["chat", "wifi", "earthquake", "gesture"]
	}
	var body := JSON.stringify(registration)
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/orchestrator/register" % url, [], body)
	if err != OK:
		print("[AuraClient] Could not register with orchestrator: %s" % err)


func _probe_backend(url: String) -> bool:
	var probe := HTTPClient.new()
	if probe.connect_to_url(url) != OK:
		return false

	var err := probe.request(HTTPClient.METHOD_GET, "/health", [])
	if err != OK:
		return false

	var start := Time.get_ticks_msec()
	while probe.get_status() == HTTPClient.STATUS_REQUESTING or probe.get_status() == HTTPClient.STATUS_BODY:
		probe.poll()
		if Time.get_ticks_msec() - start > 2000:
			return false

	if probe.get_status() != HTTPClient.STATUS_BODY:
		return false

	var chunks := []
	while probe.get_status() == HTTPClient.STATUS_BODY:
		var chunk := probe.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())

	var body := "".join(chunks)
	var data := JSON.parse_string(body)
	return data is Dictionary and data.get("status") in ["ok", "healthy"]


func _process(delta: float) -> void:
	if not _http:
		return
	var status := _http.get_status()
	if status == HTTPClient.STATUS_REQUESTING or status == HTTPClient.STATUS_BODY:
		_http.poll()
		if status == HTTPClient.STATUS_BODY:
			var chunks := []
			while _http.get_status() == HTTPClient.STATUS_BODY:
				var chunk := _http.read_response_body_chunk()
				if chunk.is_empty():
					break
				chunks.append(chunk.get_string_from_utf8())
			_handle_http_response("".join(chunks))

	if _ws and _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		_ws.poll()
		while _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
			var pkt := _ws.get_packet()
			if pkt.is_empty():
				break
			_handle_stream_message(pkt.get_string_from_utf8())


func _connect_http(url: String) -> void:
	if _http.connect_to_url(url) != OK:
		push_error("No se pudo conectar al backend AURA en %s" % url)
		disconnected.emit()


func _check_connection() -> void:
	if _busy:
		return
	_busy = true
	var err := _http.request(HTTPClient.METHOD_GET, "%s/health" % _backend_url, [])
	if err != OK:
		_busy = false
		disconnected.emit()
		_reconnect_attempts += 1
		if _reconnect_attempts >= _max_reconnect_attempts and _use_local:
			_switch_to_cloud()


func _attempt_reconnect() -> void:
	if _connected:
		return
	if _use_local:
		_connect_http(_backend_url)
	else:
		_connect_http(_cloud_url)


func _switch_to_cloud() -> void:
	if not _use_local:
		return
	_use_local = false
	_backend_url = _cloud_url
	_reconnect_attempts = 0
	print("[AuraClient] Switching to cloud backend: %s" % _backend_url)
	_connect_http(_backend_url)


func send_image(image_path: String, prompt: String = "") -> void:
	if _busy:
		return
	_busy = true
	var file := FileAccess.open(image_path, FileAccess.READ)
	if not file:
		_busy = false
		push_error("No se pudo abrir la imagen: %s" % image_path)
		return
	var bytes := file.get_buffer(file.get_length())
	var base64 := bytes.get_string_from_utf8()
	var body := JSON.stringify({
		"prompt": prompt,
		"image_base64": base64,
	})
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/chat" % _backend_url, [], body)
	if err != OK:
		_busy = false
		push_error("Error enviando imagen: %s" % err)
	else:
		media_sent.emit("image")


func send_video(video_path: String, prompt: String = "") -> void:
	if _busy:
		return
	_busy = true
	var file := FileAccess.open(video_path, FileAccess.READ)
	if not file:
		_busy = false
		push_error("No se pudo abrir el video: %s" % video_path)
		return
	var bytes := file.get_buffer(file.get_length())
	var base64 := bytes.get_string_from_utf8()
	var body := JSON.stringify({
		"prompt": prompt,
		"video_base64": base64,
	})
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/chat" % _backend_url, [], body)
	if err != OK:
		_busy = false
		push_error("Error enviando video: %s" % err)
	else:
		media_sent.emit("video")


func _handle_http_response(body: String) -> void:
	_busy = false
	if body.is_empty():
		return
	var lines := body.split("\n")
	for line in lines:
		line = line.strip_edges()
		if line.begins_with("data:"):
			var payload := line.substr(5).strip_edges()
			var data := JSON.parse_string(payload)
			if not data:
				continue
			if data is Dictionary:
				if data.has("status"):
					if data.get("status") == "ok":
						if not _connected:
							_connected = true
							connected.emit()
					else:
						if _connected:
							_connected = false
							disconnected.emit()
				if data.has("text"):
					var prompt := _last_prompt
					EventBus.chat_received.emit(prompt, str(data.get("text", "")), str(data.get("provider", "unknown")))
					_last_prompt = ""
				if data.has("token"):
					EventBus.stream_token.emit(str(data.token), bool(data.get("done", false)))
					if data.get("done"):
						EventBus.stream_token.emit("", true)
				if data.has("networks") or data.has("wifi"):
					var networks: Array = []
					if data.has("networks"):
						networks = data.networks
					elif data.has("wifi"):
						networks = data.wifi
					EventBus.wifi_update.emit(networks, data.get("zones", []), data.get("motion", []), data.get("anomalies", []))
				if data.has("events") or data.has("earthquakes"):
					var events: Array = data.get("events", [])
					if data.has("earthquakes"):
						events = data.earthquakes
					EventBus.earthquake_risk_update.emit(float(data.get("score", 0.0)), str(data.get("level", "low")), events)
				if data.has("gesture"):
					EventBus.gesture_detected.emit(str(data.gesture), float(data.get("confidence", 0.0)), int(data.get("fingers", 0)))


func send_chat(prompt: String, router: bool = true) -> void:
	if not prompt.strip_edges() or _busy:
		return
	_busy = true
	_last_prompt = prompt
	var body := JSON.stringify({"prompt": prompt, "router": router})
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/chat/stream" % _backend_url, [], body)
	if err != OK:
		_busy = false
		push_error("Error enviando chat: %s" % err)


func connect_gesture_stream() -> void:
	if _ws:
		_ws = null
	_ws = WebSocketPeer.new()
	var err := _ws.connect_to_url("%s/api/gesture/stream" % _backend_url)
	if err != OK:
		push_error("No se pudo conectar al stream de gestos: %s" % err)
		return
	connected.emit()


func connect_wifi_stream() -> void:
	if not _poll_wifi_timer.is_inside_tree():
		add_child(_poll_wifi_timer)
	_poll_wifi_timer.start()


func connect_earthquake_stream() -> void:
	if not _poll_earthquake_timer.is_inside_tree():
		add_child(_poll_earthquake_timer)
	_poll_earthquake_timer.start()


func _request_wifi() -> void:
	if _busy:
		return
	_busy = true
	var err := _http.request(HTTPClient.METHOD_GET, "%s/api/wifi/stream" % _backend_url, [])
	if err != OK:
		_busy = false


func _request_earthquakes() -> void:
	if _busy:
		return
	_busy = true
	var err := _http.request(HTTPClient.METHOD_GET, "%s/api/earthquakes/recent" % _backend_url, [])
	if err != OK:
		_busy = false


func _handle_stream_message(text: String) -> void:
	var payload := text.substr(5).strip_edges() if text.begins_with("data:") else text.strip_edges()
	var data := JSON.parse_string(payload)
	if not data:
		return
	if data.has("gesture"):
		EventBus.gesture_detected.emit(str(data.gesture), float(data.get("confidence", 0.0)), int(data.get("fingers", 0)))
	if data.has("wifi") or data.has("networks"):
		var networks: Array = data.get("networks", []) if data.has("networks") else []
		EventBus.wifi_update.emit(networks, data.get("zones", []), data.get("motion", []), data.get("anomalies", []))
	if data.has("earthquake") or data.has("events") or data.has("risk"):
		var score: float = float(data.get("score", 0.0))
		var level: String = str(data.get("level", "low"))
		var events: Array = data.get("events", [])
		if data.has("earthquake"):
			events = data.earthquake
		EventBus.earthquake_risk_update.emit(score, level, events)
		if data.has("token"):
			EventBus.stream_token.emit(str(data.token), bool(data.get("done", false)))
			if data.get("done"):
				EventBus.stream_token.emit("", true)


func is_connected() -> bool:
	return _connected


func set_backend_url(url: String) -> void:
	_backend_url = url
	if _http:
		_connect_http(_backend_url)


func get_backend_url() -> String:
	return _backend_url


func is_using_local() -> bool:
	return _use_local


func get_telemetry() -> Dictionary:
	if not _http:
		return {}
	var url := "%s/api/system/telemetry" % _backend_url
	var err := _http.request(HTTPClient.METHOD_GET, url, [])
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 5000:
			return {}
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	return data if data is Dictionary else {}


var _sync_device_id := "godot-client"
var _sync_role := "pc"
var _sync_timer: Timer
var _last_known_devices: Dictionary = {}


func init_sync(device_id: String, role: String = "pc") -> void:
	_sync_device_id = device_id
	_sync_role = role
	_sync_timer = Timer.new()
	_sync_timer.wait_time = 2.0
	_sync_timer.timeout.connect(_tick_sync)
	add_child(_sync_timer)
	_register_sync()


func _register_sync() -> void:
	if not _http:
		return
	var payload := JSON.stringify({
		"device_id": _sync_device_id,
		"role": _sync_role,
		"state": {
			"backend_url": _backend_url,
			"connected": _connected,
			"use_local": _use_local,
		},
		"last_seen": Time.get_unix_time_from_system(),
	})
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/sync/register" % _backend_url, [], payload)
	if err != OK:
		print("[Sync] register failed: %s" % err)


func _tick_sync() -> void:
	if not _http:
		return
	var state_payload := JSON.stringify({
		"device_id": _sync_device_id,
		"role": _sync_role,
		"state": {
			"backend_url": _backend_url,
			"connected": _connected,
			"use_local": _use_local,
			"last_prompt": _last_prompt,
		},
	})
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/sync/state" % _backend_url, [], state_payload)
	if err != OK:
		print("[Sync] update failed: %s" % err)

	var list_err := _http.request(HTTPClient.METHOD_GET, "%s/api/sync/devices" % _backend_url, [])
	if list_err != OK:
		return
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	if data is Dictionary and data.has("devices"):
		_last_known_devices.clear()
		for d in data.devices:
			if d is Dictionary:
				_last_known_devices[d.device_id] = d


func get_sync_devices() -> Dictionary:
	return _last_known_devices


func send_sync_command(target_device: String, command: String, payload: Dictionary = {}) -> Dictionary:
	if not _http:
		return {}
	var body := JSON.stringify({
		"target_device": target_device,
		"command": command,
		"payload": payload,
	})
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/sync/command" % _backend_url, [], body)
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return {}
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	return data if data is Dictionary else {}


func poll_sync_commands() -> Array:
	if not _http:
		return []
	var url := "%s/api/sync/commands/%s" % [_backend_url, _sync_device_id]
	var err := _http.request(HTTPClient.METHOD_GET, url, [])
	if err != OK:
		return []
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return []
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	if data is Dictionary and data.has("commands"):
		return data.commands
	return []


func start_sync() -> void:
	if _sync_timer:
		_sync_timer.start()


func stop_sync() -> void:
	if _sync_timer:
		_sync_timer.stop()


func scan_wifi() -> Dictionary:
	if not _http:
		return {}
	var url := "%s/api/wifi/scan" % _backend_url
	var body := JSON.stringify({})
	var err := _http.request(HTTPClient.METHOD_POST, url, [], body)
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 5000:
			return {}
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	return data if data is Dictionary else {}


func smart_route_query(query: String, force_route: String = "") -> Dictionary:
	if not _http:
		return {}
	var payload := {"query": query}
	if not force_route.is_empty():
		payload["force_route"] = force_route
	var body := JSON.stringify(payload)
	var err := _http.request(HTTPClient.METHOD_POST, "%s/api/brain/route/query" % _backend_url, [], body)
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return {}
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	return data if data is Dictionary else {}


func get_route_status() -> Dictionary:
	if not _http:
		return {}
	var err := _http.request(HTTPClient.METHOD_GET, "%s/api/brain/route/status" % _backend_url, [])
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return {}
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	return data if data is Dictionary else {}


func get_route_history(limit: int = 10) -> Array:
	if not _http:
		return []
	var url := "%s/api/brain/route/history?limit=%d" % [_backend_url, limit]
	var err := _http.request(HTTPClient.METHOD_GET, url, [])
	if err != OK:
		return []
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return []
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	if data is Dictionary and data.has("history"):
		return data.history
	return []


func request_json(path: String, method: int = HTTPClient.METHOD_GET) -> Dictionary:
	if not _http:
		return {}
	var url := "%s%s" % [_backend_url, path]
	var err := _http.request(HTTPClient.METHOD_GET, url, [])
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while _http.get_status() == HTTPClient.STATUS_REQUESTING or _http.get_status() == HTTPClient.STATUS_BODY:
		_http.poll()
		if Time.get_ticks_msec() - start > 2000:
			return {}
	var chunks := []
	while _http.get_status() == HTTPClient.STATUS_BODY:
		var chunk := _http.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body_text := "".join(chunks)
	var data := JSON.parse_string(body_text)
	return data if data is Dictionary else {}
