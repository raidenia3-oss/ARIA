extends Control

var title_label: Label
var last_route_label: Label
var urgent_label: Label
var quality_label: Label
var fresh_label: Label
var cache_label: Label
var server_load: Label

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
	title_label.text = "[ROUTER] ADAPTIVE"
	title_label.add_theme_color_override("font_color", Color(0.22, 0.74, 0.98))
	vbox.add_child(title_label)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	last_route_label = Label.new()
	last_route_label.text = "Last Route: --"
	vbox.add_child(last_route_label)

	urgent_label = Label.new()
	urgent_label.text = "Urgent: --"
	vbox.add_child(urgent_label)

	quality_label = Label.new()
	quality_label.text = "Quality: --"
	vbox.add_child(quality_label)

	fresh_label = Label.new()
	fresh_label.text = "Fresh: --"
	vbox.add_child(fresh_label)

	cache_label = Label.new()
	cache_label.text = "Cache: --"
	vbox.add_child(cache_label)

	server_load = Label.new()
	server_load.text = "Server Load: --"
	vbox.add_child(server_load)

func _update():
	if not dashboard:
		return
	var status: Dictionary = dashboard.query_api("/api/brain/route/status")
	if status.is_empty():
		return

	last_route_label.text = "Last Route: %s" % str(status.get("last_route", "--"))
	server_load.text = "Server Load: %s" % str(status.get("server_load", "--"))

	var available = status.get("available_targets", [])
	urgent_label.text = "Urgent: %s" % ("SERVER" if "server" in available else "N/A")
	quality_label.text = "Quality: %s" % ("PC" if "pc" in available else "N/A")
	fresh_label.text = "Fresh: %s" % ("API" if "api" in available else "N/A")
	cache_label.text = "Cache: %s" % ("ON" if "cache" in available else "OFF")
