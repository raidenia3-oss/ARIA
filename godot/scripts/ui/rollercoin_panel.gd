extends Control
## Panel de Rollercoin para AURA
## Muestra estado del bot, balance, earnings, meta

class_name RollercoinPanel

# UI Elements
var status_label: Label
var balance_label: Label
var earnings_label: Label
var games_label: Label
var goal_label: Label
var goal_input: LineEdit
var start_btn: Button
var stop_btn: Button
var claim_btn: Button
var status_indicator: ColorRect

# Cliente HTTP
var http_client: HTTPClient

# Timer para polling
var update_timer: Timer

# Estado actual
var bot_running: bool = false
var current_balance: float = 0.0
var earnings_per_min: float = 0.0
var games_played: int = 0
var goal: float = 0.0

# Colores
var accent_color: Color = Color(0.22, 0.88, 1.0, 1.0)  # Cyan
var success_color: Color = Color(0.2, 1.0, 0.8, 1.0)   # Verde
var error_color: Color = Color(1.0, 0.2, 0.2, 1.0)     # Rojo
var bg_color: Color = Color(0.06, 0.09, 0.16, 0.95)    # Dark

func _ready():
	http_client = HTTPClient.new()
	
	# Crear timer
	update_timer = Timer.new()
	add_child(update_timer)
	update_timer.timeout.connect(_fetch_status)
	update_timer.start(2.0)  # Actualizar cada 2 segundos
	
	# Construir UI
	_build_ui()

func _build_ui():
	"""Construir interfaz del panel"""
	# Panel principal
	var main_panel = PanelContainer.new()
	main_panel.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	main_panel.anchor_left = 0.7
	main_panel.anchor_top = 0.7
	main_panel.anchor_right = 1.0
	main_panel.anchor_bottom = 1.0
	main_panel.offset_left = -10
	main_panel.offset_top = -10
	main_panel.offset_right = -10
	main_panel.offset_bottom = -10
	add_child(main_panel)
	
	# Estilo panel
	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(bg_color.r, bg_color.g, bg_color.b, 0.85)
	panel_style.border_color = accent_color
	panel_style.set_border_enabled_all(true)
	panel_style.border_width_left = 2
	panel_style.border_width_right = 2
	panel_style.border_width_top = 2
	panel_style.border_width_bottom = 2
	main_panel.add_theme_stylebox_override("panel", panel_style)
	
	# VBox para contenido
	var vbox = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	main_panel.add_child(vbox)
	
	# ===== TITULO =====
	var title = Label.new()
	title.text = "[ROLLERCOIN BOT]"
	title.add_theme_color_override("font_color", accent_color)
	title.add_theme_font_size_override("font_size", 14)
	vbox.add_child(title)
	
	# ===== STATUS INDICATOR =====
	var status_container = HBoxContainer.new()
	status_container.add_theme_constant_override("separation", 8)
	vbox.add_child(status_container)
	
	status_indicator = ColorRect.new()
	status_indicator.color = error_color
	status_indicator.custom_minimum_size = Vector2(12, 12)
	status_container.add_child(status_indicator)
	
	status_label = Label.new()
	status_label.text = "STATUS: STOPPED"
	status_label.add_theme_font_size_override("font_size", 11)
	status_container.add_child(status_label)
	
	# ===== BALANCE =====
	balance_label = Label.new()
	balance_label.text = "BALANCE: $0.00"
	balance_label.add_theme_font_size_override("font_size", 12)
	balance_label.add_theme_color_override("font_color", success_color)
	vbox.add_child(balance_label)
	
	# ===== EARNINGS =====
	earnings_label = Label.new()
	earnings_label.text = "EARNINGS: $0.00/min"
	earnings_label.add_theme_font_size_override("font_size", 11)
	vbox.add_child(earnings_label)
	
	# ===== GAMES =====
	games_label = Label.new()
	games_label.text = "GAMES: 0"
	games_label.add_theme_font_size_override("font_size", 11)
	vbox.add_child(games_label)
	
	# ===== META =====
	var goal_container = VBoxContainer.new()
	goal_container.add_theme_constant_override("separation", 4)
	vbox.add_child(goal_container)
	
	goal_label = Label.new()
	goal_label.text = "GOAL: None"
	goal_label.add_theme_font_size_override("font_size", 11)
	goal_container.add_child(goal_label)
	
	var goal_input_container = HBoxContainer.new()
	goal_input_container.add_theme_constant_override("separation", 4)
	goal_container.add_child(goal_input_container)
	
	goal_input = LineEdit.new()
	goal_input.placeholder_text = "Meta ($)"
	goal_input.custom_minimum_size = Vector2(100, 24)
	goal_input_container.add_child(goal_input)
	
	var set_goal_btn = Button.new()
	set_goal_btn.text = "SET"
	set_goal_btn.custom_minimum_size = Vector2(40, 24)
	set_goal_btn.pressed.connect(_on_set_goal)
	goal_input_container.add_child(set_goal_btn)
	
	# ===== BUTTONS =====
	var btn_container = HBoxContainer.new()
	btn_container.add_theme_constant_override("separation", 5)
	vbox.add_child(btn_container)
	
	start_btn = Button.new()
	start_btn.text = "START"
	start_btn.custom_minimum_size = Vector2(60, 28)
	start_btn.pressed.connect(_on_start)
	btn_container.add_child(start_btn)
	
	stop_btn = Button.new()
	stop_btn.text = "STOP"
	stop_btn.custom_minimum_size = Vector2(60, 28)
	stop_btn.pressed.connect(_on_stop)
	stop_btn.disabled = true
	btn_container.add_child(stop_btn)
	
	claim_btn = Button.new()
	claim_btn.text = "CLAIM"
	claim_btn.custom_minimum_size = Vector2(60, 28)
	claim_btn.pressed.connect(_on_claim)
	btn_container.add_child(claim_btn)

func _on_start():
	"""Iniciar bot"""
	var goal_amount = goal_input.text.to_float()
	
	# POST a /api/rollercoin/start
	_http_request("POST", "/api/rollercoin/start", {
		"amount": goal_amount if goal_amount > 0 else null
	})
	
	start_btn.disabled = true
	stop_btn.disabled = false
	goal = goal_amount

func _on_stop():
	"""Detener bot"""
	# POST a /api/rollercoin/stop
	_http_request("POST", "/api/rollercoin/stop", {})
	
	start_btn.disabled = false
	stop_btn.disabled = true

func _on_set_goal():
	"""Cambiar meta"""
	var goal_amount = goal_input.text.to_float()
	if goal_amount > 0:
		_http_request("POST", "/api/rollercoin/set_goal", {
			"amount": goal_amount
		})
		goal = goal_amount
		goal_label.text = "GOAL: $%.2f" % goal

func _on_claim():
	"""Reclamar rewards manualmente"""
	_http_request("POST", "/api/rollercoin/claim_rewards", {})

func _fetch_status():
	"""Obtener estado del bot"""
	_http_request("GET", "/api/rollercoin/status", {})

func _http_request(method: String, endpoint: String, body: Dictionary = {}):
	"""Hacer request HTTP al backend"""
	var error = http_client.connect_to_host("127.0.0.1", 8000)
	
	if error != OK:
		return
	
	var headers = ["User-Agent: Godot/4.3", "Content-Type: application/json"]
	
	if method == "GET":
		http_client.request(HTTPClient.METHOD_GET, endpoint, headers)
	elif method == "POST":
		var json_body = JSON.stringify(body) if body else "{}"
		http_client.request(HTTPClient.METHOD_POST, endpoint, headers, json_body)
	
	# Esperar respuesta
	var start = Time.get_ticks_msec()
	while http_client.get_status() == HTTPClient.STATUS_REQUESTING:
		if Time.get_ticks_msec() - start > 5000:
			http_client.close()
			return
	
	if http_client.get_status() == HTTPClient.STATUS_BODY:
		var response = http_client.read_response_body_chunk()
		if response:
			var json = JSON.parse_string(response.get_string_from_utf8())
			if json and endpoint.contains("status"):
				_update_display(json)
	
	http_client.close()

func _update_display(status: Dictionary):
	"""Actualizar display con datos del bot"""
	bot_running = status.get("running", false)
	
	if bot_running:
		status_indicator.color = success_color
		status_label.text = "STATUS: RUNNING"
	else:
		status_indicator.color = error_color
		status_label.text = "STATUS: STOPPED"
	
	var stats = status.get("stats", {})
	
	current_balance = stats.get("balance", 0.0)
	earnings_per_min = stats.get("earnings_per_min", 0.0)
	games_played = stats.get("games_played", 0)
	
	balance_label.text = "BALANCE: $%.2f" % current_balance
	earnings_label.text = "EARNINGS: $%.2f/min" % earnings_per_min
	games_label.text = "GAMES: %d" % games_played
	
	# Checkear meta
	if stats.get("goal_reached", false):
		goal_label.text = "GOAL: ✓ REACHED!"
		goal_label.add_theme_color_override("font_color", success_color)

func _exit_tree():
	if update_timer:
		update_timer.queue_free()
	if http_client:
		http_client.disconnect_from_host()
