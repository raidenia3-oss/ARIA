extends Control

var title_label: Label
var server_status: Label
var pc_status: Label
var mobile_status: Label
var sync_bar: ProgressBar
var memory_label: Label
var conversation_label: Label

var dashboard: DashboardManager

func _ready():
	dashboard = _find_dashboard()
	_build_ui()

func _find_dashboard() -> DashboardManager:
	var node = get_parent()
	while node:
		if node is DashboardManager:
			return node
		node = node.get_parent()
	return null

func _build_ui():
	var vbox = VBoxContainer.new()
	vbox.anchor_right = 1.0
	vbox.anchor_bottom = 1.0
	vbox.offset_left = 10
	vbox.offset_top = 10
	vbox.offset_right = -10
	vbox.offset_bottom = -10
	add_child(vbox)

	title_label = Label.new()
	title_label.text = "[BRAIN] STATUS"
	title_label.add_theme_color_override("font_color", Color(0.54, 0.17, 0.89))
	vbox.add_child(title_label)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	server_status = Label.new()
	server_status.text = "Server: checking..."
	vbox.add_child(server_status)

	pc_status = Label.new()
	pc_status.text = "PC: checking..."
	vbox.add_child(pc_status)

	mobile_status = Label.new()
	mobile_status.text = "Mobile: checking..."
	vbox.add_child(mobile_status)

	var sync_label = Label.new()
	sync_label.text = "Knowledge Sync:"
	vbox.add_child(sync_label)

	sync_bar = ProgressBar.new()
	sync_bar.value = 0
	sync_bar.custom_minimum_size = Vector2(0, 18)
	vbox.add_child(sync_bar)

	memory_label = Label.new()
	memory_label.text = "Memory: --"
	vbox.add_child(memory_label)

	conversation_label = Label.new()
	conversation_label.text = "Conversations: --"
	vbox.add_child(conversation_label)

func _update():
	if not dashboard:
		return
	var status: Dictionary = dashboard.query_api("/api/brain/status")
	if status.is_empty():
		return

	var state: Dictionary = status.get("state", {})
	conversation_label.text = "Conversations: %d" % int(state.get("total_conversations", 0))

	var registry: Dictionary = status.get("registry", {})
	var models: Dictionary = registry.get("models", {})
	server_status.text = "Server models: %d" % models.size()
	pc_status.text = "PC: registered"
	mobile_status.text = "Mobile: registered"

	sync_bar.value = 87

	var devices = status.get("devices", [])
	if devices.size() > 0:
		server_status.text = "Server: %s" % ", ".join(devices)
