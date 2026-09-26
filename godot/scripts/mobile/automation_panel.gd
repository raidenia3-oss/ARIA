extends Control
class_name MobileAutomationPanel

var apps_list: ItemList
var earnings_label: Label
var status_label: Label
var start_btn: Button
var stop_btn: Button
var optimize_btn: Button

var current_apps: Array = []
var daily_earnings: float = 0.0
var is_running: bool = false

func _ready() -> void:
	_build_ui()
	_load_apps()
	_update_status()

func _build_ui() -> void:
	var vbox = VBoxContainer.new()
	add_child(vbox)

	var title = Label.new()
	title.text = "[MOBILE] AUTOMATION"
	title.add_theme_font_size_override("font_size", 20)
	vbox.add_child(title)

	status_label = Label.new()
	status_label.text = "Status: IDLE"
	vbox.add_child(status_label)

	earnings_label = Label.new()
	earnings_label.text = "Today: $0.00"
	earnings_label.add_theme_color_override("font_color", Color.GREEN)
	vbox.add_child(earnings_label)

	var apps_label = Label.new()
	apps_label.text = "Apps disponibles:"
	vbox.add_child(apps_label)

	apps_list = ItemList.new()
	apps_list.custom_minimum_size = Vector2(0, 180)
	vbox.add_child(apps_list)

	var btn_hbox = HBoxContainer.new()
	vbox.add_child(btn_hbox)

	start_btn = Button.new()
	start_btn.text = "Start Automation"
	start_btn.pressed.connect(_on_start)
	btn_hbox.add_child(start_btn)

	stop_btn = Button.new()
	stop_btn.text = "Stop Automation"
	stop_btn.disabled = true
	stop_btn.pressed.connect(_on_stop)
	btn_hbox.add_child(stop_btn)

	optimize_btn = Button.new()
	optimize_btn.text = "Optimize"
	optimize_btn.pressed.connect(_on_optimize)
	btn_hbox.add_child(optimize_btn)

	var toggle_hbox = HBoxContainer.new()
	vbox.add_child(toggle_hbox)

	var enable_all = Button.new()
	enable_all.text = "Enable All"
	enable_all.pressed.connect(_on_enable_all)
	toggle_hbox.add_child(enable_all)

	var disable_all = Button.new()
	disable_all.text = "Disable All"
	disable_all.pressed.connect(_on_disable_all)
	toggle_hbox.add_child(disable_all)

func _load_apps() -> void:
	var result = _get_json("/api/mobile/apps/available")
	if result.is_empty():
		return
	current_apps = result.get("apps", [])
	apps_list.clear()
	for app in current_apps:
		var text = "%s - $%.2f/h" % [app.get("name", "Unknown"), app.get("earning_per_hour", 0.0)]
		apps_list.add_item(text)

func _on_start() -> void:
	var result = _post_json("/api/mobile/automation/start", {})
	if result.get("status") == "started":
		is_running = true
		start_btn.disabled = true
		stop_btn.disabled = false
		status_label.text = "Status: RUNNING"
		status_label.add_theme_color_override("font_color", Color.GREEN)
		print("Mobile automation started")

func _on_stop() -> void:
	var result = _post_json("/api/mobile/automation/stop", {})
	if result.get("status") == "stopped":
		is_running = false
		start_btn.disabled = false
		stop_btn.disabled = true
		status_label.text = "Status: STOPPED"
		status_label.add_theme_color_override("font_color", Color.RED)
		print("Mobile automation stopped")

func _on_optimize() -> void:
	var result = _post_json("/api/mobile/automation/optimize", {})
	if result.get("status") == "optimized":
		var top_apps = result.get("top_apps", [])
		print("Mobile optimized for:")
		for app_name in top_apps:
			print("  - %s" % app_name)

func _on_enable_all() -> void:
	for app in current_apps:
		_post_json("/api/mobile/apps/%s/enable" % app.get("name", ""), {})
	print("Mobile: all apps enabled")

func _on_disable_all() -> void:
	for app in current_apps:
		_post_json("/api/mobile/apps/%s/disable" % app.get("name", ""), {})
	print("Mobile: all apps disabled")

func _update_status() -> void:
	var status = _get_json("/api/mobile/automation/status")
	if status.is_empty():
		return
	daily_earnings = float(status.get("daily_earnings", 0.0))
	earnings_label.text = "Today: $%.2f" % daily_earnings
	if status.get("status") == "running":
		status_label.text = "Status: RUNNING (%s apps)" % status.get("active_apps", 0)
		status_label.add_theme_color_override("font_color", Color.GREEN)

func _get_json(endpoint: String) -> Dictionary:
	var client = HTTPClient.new()
	var err = client.connect_to_host("127.0.0.1", 8000)
	if err != OK:
		return {}
	err = client.request(HTTPClient.METHOD_GET, endpoint, [])
	if err != OK:
		return {}
	var start = Time.get_ticks_msec()
	while client.get_status() == HTTPClient.STATUS_REQUESTING or client.get_status() == HTTPClient.STATUS_BODY:
		client.poll()
		if Time.get_ticks_msec() - start > 20000:
			return {}
	var chunks = []
	while client.get_status() == HTTPClient.STATUS_BODY:
		var chunk = client.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var text = "".join(chunks)
	var data = JSON.parse_string(text)
	return data if data is Dictionary else {}

func _post_json(endpoint: String, payload: Dictionary) -> Dictionary:
	var client = HTTPClient.new()
	var err = client.connect_to_host("127.0.0.1", 8000)
	if err != OK:
		return {}
	var body = JSON.stringify(payload)
	err = client.request(HTTPClient.METHOD_POST, endpoint, ["Content-Type: application/json"], body)
	if err != OK:
		return {}
	var start = Time.get_ticks_msec()
	while client.get_status() == HTTPClient.STATUS_REQUESTING or client.get_status() == HTTPClient.STATUS_BODY:
		client.poll()
		if Time.get_ticks_msec() - start > 20000:
			return {}
	var chunks = []
	while client.get_status() == HTTPClient.STATUS_BODY:
		var chunk = client.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var text = "".join(chunks)
	var data = JSON.parse_string(text)
	return data if data is Dictionary else {}
