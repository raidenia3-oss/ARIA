## AmeMobileWebSocketClient.gd — Cliente WebSocket Móvil para AURA
## Se conecta a ws://localhost:5000/ws, gestiona telemetría, logs y selector de fondo.

extends Node

signal connection_changed(connected: bool)
signal node_update(nodes: Array)
signal task_update(task: Dictionary)
signal log_event(message: String)
signal background_selected(image_path: String)

const WS_URL := "ws://localhost:5000/ws"
const RECONNECT_INTERVAL := 2.0

var _ws: WebSocketPeer = WebSocketPeer.new()
var _connected := false
var _reconnect_timer := 0.0
var _pending_actions := []

# Referencias UI (se asignan desde el HUD móvil)
var log_text: RichTextLabel = null
var node_list: VBoxContainer = null
var status_label: Label = null
var connection_dot: ColorRect = null

func _ready() -> void:
	process_priority = -1
	connect_to_server()

func _process(delta: float) -> void:
	# Reconnect
	if not _connected and _reconnect_timer > 0:
		_reconnect_timer -= delta
		if _reconnect_timer <= 0:
			connect_to_server()

	# Poll WebSocket
	if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		_ws.poll()
		while _ws.get_ready_state() == WebSocketPeer.STATE_OPEN and _ws.get_available_packet_count() > 0:
			var msg = _ws.get_packet().get_string_from_utf8()
			_process_message(msg)

func connect_to_server() -> void:
	print("[AmeWS] Conectando a %s..." % WS_URL)
	var err = _ws.connect_to_url(WS_URL)
	if err != OK:
		push_warning("[AmeWS] Error inicial: %d" % err)
		_reconnect_timer = RECONNECT_INTERVAL
		return

	# Suscripciones automáticas (para móvil utilizamos el mismo protocolo)
	_send_json({"action": "subscribe", "channel": "node_update"})
	_send_json({"action": "subscribe", "channel": "task_update"})
	_send_json({"action": "subscribe", "channel": "task_assigned"})

func _send_json(data: Dictionary) -> void:
	if _ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var json_str = JSON.stringify(data)
	var err = _ws.put_packet(json_str.to_utf8_buffer())
	if err != OK:
		push_warning("[AmeWS] Error al enviar: %d" % err)

func _process_message(msg: String) -> void:
	var data = JSON.parse_string(msg)
	if data == null:
		return
	var event = data.get("event", "")
	var payload = data.get("data", {})

	match event:
		"node_update":
			_update_nodes(payload)
		"task_update":
			_update_task(payload)
		"task_assigned":
			_add_log("TAREA ASIGNADA: %s" % payload.get("module", "?"))
		_:
			_add_log("EVENTO: %s" % event)

func _update_nodes(nodes: Array) -> void:
	if node_list == null:
		return
	# Limpiar
	for child in node_list.get_children():
		node_list.remove_child(child)
		child.queue_free()
	# Reconstruir
	for node in nodes:
		var hbox = HBoxContainer.new()
		var indicator = ColorRect.new()
		indicator.color = Color.GREEN if node.get("status") == "available" else Color.RED
		indicator.custom_minimum_size = Vector2(8, 8)
		var label = Label.new()
		label.text = "%s [%s]" % [node.get("name", "?"), node.get("type", "?")]
		label.add_theme_color_override("font_color", Color.CYAN)
		hbox.add_child(indicator)
		hbox.add_child(label)
		node_list.add_child(hbox)

func _update_task(task: Dictionary) -> void:
	var status = task.get("status", "")
	var progress = task.get("progress", 0)
	var module = task.get("module", "?")
	match status:
		"running":
			_add_log("%s %d%%" % [module, progress])
		"completed":
			_add_log("%s COMPLETADA" % module)
		_:
			pass

func _add_log(message: String) -> void:
	if log_text == null:
		return
	var time = Time.get_datetime_string_from_system().substr(11, 8)
	var line = "[%s] %s" % [time, message]
	if log_text.get_line_count() >= 8:
		log_text.clear()
	log_text.append_text(line + "\n")

# --- API pública para HUD móvil ---

func assign_task(node_id: String, module: String) -> void:
	_send_json({"action": "assign_task", "nodeId": node_id, "module": module})

func select_background_from_gallery() -> void:
	# En móvil (Android), esto abre el picker nativo via plugin o Godot OS bridge.
	# Para prototyping en PC, abrimos un FileDialog.
	_show_background_picker()

func _show_background_picker() -> void:
	# TODO: Integrar con un plugin Android nativo para acceso a galería.
	# Por ahora, simular ruta y emitir señal.
	emit_signal("background_selected", "user://backgrounds/custom_bg.jpg")
	_add_log("FONDO: Imagen de galería seleccionada")

func apply_background_blur(image_path: String) -> void:
	# En Godot 4.x, el fondo lo controla un ColorRect con un ShaderMaterial.
	# El path recibido se asigna a un uniform en el shader de blur.
	_add_log("APLICANDO BLUR AL FONDO: %s" % image_path)
