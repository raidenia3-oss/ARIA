extends Control
class_name DashboardManager

var brain_panel: Control
var routing_panel: Control
var treasury_panel: Control
var training_panel: Control
var rollercoin_panel: Control
var infrastructure_panel: Control
var console_panel: Control
var central_vis: Control

var api_client: HTTPClient
var api_url: String = "http://127.0.0.1:8000"

var update_timer: Timer
var update_interval: float = 2.0

var console_logs: PackedStringArray = []
var max_logs: int = 50

func _ready() -> void:
	_setup_ui()
	_setup_timers()
	_log("Dashboard initialized")

func _setup_ui() -> void:
	_create_brain_panel()
	_create_routing_panel()
	_create_treasury_panel()
	_create_central_visualization()
	_create_training_panel()
	_create_rollercoin_panel()
	_create_infrastructure_panel()
	_create_console_panel()

func _setup_timers() -> void:
	update_timer = Timer.new()
	add_child(update_timer)
	update_timer.timeout.connect(_update_all_panels)
	update_timer.start(update_interval)

func _create_brain_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	panel.anchor_right = 0.25
	panel.anchor_bottom = 0.25
	panel.custom_minimum_size = Vector2(280, 240)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/brain_status_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.54, 0.17, 0.89))
	brain_panel = panel

func _create_routing_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_CENTER)
	panel.anchor_left = 0.375
	panel.anchor_right = 0.625
	panel.anchor_bottom = 0.25
	panel.custom_minimum_size = Vector2(280, 240)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/routing_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.22, 0.74, 0.98))
	routing_panel = panel

func _create_treasury_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	panel.anchor_left = 0.75
	panel.anchor_bottom = 0.25
	panel.custom_minimum_size = Vector2(280, 240)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/treasury_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.98, 0.75, 0.14))
	treasury_panel = panel

func _create_central_visualization() -> void:
	var vis = Control.new()
	vis.set_anchors_preset(Control.PRESET_CENTER)
	vis.custom_minimum_size = Vector2(500, 360)
	vis.anchor_left = 0.30
	vis.anchor_top = 0.28
	vis.anchor_right = 0.70
	vis.anchor_bottom = 0.68
	add_child(vis)

	var script = preload("res://scripts/dashboard/central_visualization.gd")
	vis.set_script(script)

	central_vis = vis

func _create_training_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	panel.anchor_top = 0.75
	panel.anchor_right = 0.25
	panel.custom_minimum_size = Vector2(280, 240)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/training_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.66, 0.33, 0.97))
	training_panel = panel

func _create_rollercoin_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_BOTTOM_CENTER)
	panel.anchor_left = 0.375
	panel.anchor_top = 0.75
	panel.anchor_right = 0.625
	panel.custom_minimum_size = Vector2(280, 240)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/rollercoin_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.86, 0.15, 0.15))
	rollercoin_panel = panel

func _create_infrastructure_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	panel.anchor_left = 0.75
	panel.anchor_top = 0.75
	panel.custom_minimum_size = Vector2(280, 240)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/infrastructure_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.07, 0.73, 0.51))
	infrastructure_panel = panel

func _create_console_panel() -> void:
	var panel = PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	panel.anchor_left = 0.0
	panel.anchor_right = 1.0
	panel.anchor_top = 0.93
	panel.custom_minimum_size = Vector2(0, 100)
	add_child(panel)

	var script = preload("res://scripts/dashboard/panels/console_log_panel.gd")
	panel.set_script(script)

	_style_panel_border(panel, Color(0.05, 0.05, 0.05))
	console_panel = panel

func _style_panel_border(panel: PanelContainer, border_color: Color) -> void:
	var style_box = StyleBoxFlat.new()
	style_box.bg_color = Color(0.06, 0.09, 0.16, 0.85)
	style_box.border_color = border_color
	style_box.set_border_enabled_all(true)
	style_box.border_width_left = 2
	style_box.border_width_right = 2
	style_box.border_width_top = 2
	style_box.border_width_bottom = 2
	style_box.shadow_color = border_color * Color(1, 1, 1, 0.35)
	style_box.shadow_size = 4
	panel.add_theme_stylebox_override("panel", style_box)

func _update_all_panels() -> void:
	if brain_panel and brain_panel.has_method("_update"):
		brain_panel._update()
	if routing_panel and routing_panel.has_method("_update"):
		routing_panel._update()
	if treasury_panel and treasury_panel.has_method("_update"):
		treasury_panel._update()
	if training_panel and training_panel.has_method("_update"):
		training_panel._update()
	if rollercoin_panel and rollercoin_panel.has_method("_update"):
		rollercoin_panel._update()
	if infrastructure_panel and infrastructure_panel.has_method("_update"):
		infrastructure_panel._update()
	if central_vis and central_vis.has_method("_update"):
		central_vis._update()

func _log(message: String) -> void:
	var timestamp = Time.get_ticks_msec() / 1000.0
	var formatted = "[%.2f] %s" % [timestamp, message]

	console_logs.append(formatted)
	if console_logs.size() > max_logs:
		console_logs.remove_at(0)

	if console_panel and console_panel.has_method("_add_log"):
		console_panel._add_log(formatted)

func log(message: String) -> void:
	_log(message)

func query_api(endpoint: String) -> Dictionary:
	var aura_client = get_node_or_null("/root/AuraClient")
	if not aura_client:
		aura_client = get_node_or_null("/root/Main/AuraClient")
	if not aura_client:
		aura_client = get_node_or_null("../AuraClient")
	if aura_client and aura_client.has_method("request_json"):
		return aura_client.request_json(endpoint)
	return {}
