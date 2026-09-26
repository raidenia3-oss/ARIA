## NetworkController.gd — Cliente WebSocket para AURA Backend
## Se conecta a ws://localhost:3000 para recibir telemetría y eventos en tiempo real.

extends Node

signal connection_changed(connected: bool)
signal node_update(nodes: Array)
signal task_update(task: Dictionary)
signal log_event(message: String)

var _ws_client: WebSocketClient = WebSocketClient()
var _url: String = "ws://localhost:3000"
var _reconnect_timer: float = 0.0
var _reconnect_interval: float = 2.0
var _connected: bool = false

func _ready() -> void:
	_ws_client.connect("connection_established", _on_connected)
	_ws_client.connect("connection_closed", _on_disconnected)
	_ws_client.connect("connection_error", _on_error)
	_ws_client.connect("data_received", _on_data_received)

	connect_to_server()
	print("[NetworkController] Inicializado — Objetivo: %s" % _url)

func _process(delta: float) -> void:
	if not _connected and _reconnect_timer > 0:
		_reconnect_timer -= delta
		if _reconnect_timer <= 0:
			connect_to_server()

	_ws_client.poll()

func connect_to_server() -> void:
	print("[NetworkController] Conectando a %s..." % _url)
	var err = _ws_client.connect_to_url(_url)
	if err != OK:
		push_error("[NetworkController] Error de conexión inicial: %d" % err)
		_reconnect_timer = _reconnect_interval

func _on_connected(protocol: String) -> void:
	_connected = true
	_reconnect_timer = 0.0
	connection_changed.emit(true)
	print("[NetworkController] Conectado — Protocolo: %s" % protocol)
	add_log("CONECTADO AL BACKEND AURA")

func _on_disconnected(clean_close: bool = false) -> void:
	_connected = false
	connection_changed.emit(false)
	print("[NetworkController] Desconectado (clean=%s)" % str(clean_close))
	add_log("DESCONECTADO — REINTENTANDO...")
	_reconnect_timer = _reconnect_interval

func _on_error() -> void:
	_connected = false
	connection_changed.emit(false)
	print("[NetworkController] Error de conexión")
	_reconnect_timer = _reconnect_interval

func _on_data_received() -> void:
	var message = _ws_client.get_peer(1).get_packet().get_string_from_utf8()
	var data = JSON.parse_string(message)
	if data == null:
		return

	var event = data.get("event", "")
	var payload = data.get("data", {})

	match event:
		"node_update":
			node_update.emit(payload)
		"task_update":
			task_update.emit(payload)
		"task_assigned":
			add_log("TAREA ASIGNADA: %s" % payload.get("module", "?"))
		_:
			pass

func send_subscribe(channel: String) -> void:
	if not _connected:
		return
	var msg = {
		"action": "subscribe",
		"channel": channel
	}
	_send_json(msg)

func send_assign_task(node_id: String, module: String) -> void:
	if not _connected:
		return
	var msg = {
		"action": "assign_task",
		"nodeId": node_id,
		"module": module
	}
	_send_json(msg)

func _send_json(data: Dictionary) -> void:
	var json_str = JSON.stringify(data)
	var err = _ws_client.get_peer(1).put_packet(json_str.to_utf8_buffer())
	if err != OK:
		push_warning("[NetworkController] Error al enviar: %d" % err)

func add_log(message: String) -> void:
	log_event.emit(message)

func is_connected() -> bool:
	return _connected
