extends Control

var title_label: Label
var server_uptime: Label
var backup_status: Label
var api_health: Label

func _ready():
	_build_ui()

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
	title_label.text = "[INFRA] STATUS"
	title_label.add_theme_color_override("font_color", Color(0.07, 0.73, 0.51))
	vbox.add_child(title_label)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	server_uptime = Label.new()
	server_uptime.text = "Server Uptime: --"
	vbox.add_child(server_uptime)

	backup_status = Label.new()
	backup_status.text = "Backup: --"
	vbox.add_child(backup_status)

	api_health = Label.new()
	api_health.text = "APIs: --"
	vbox.add_child(api_health)

func _update():
	pass
