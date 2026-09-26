extends Control

var log_text: RichTextLabel
var console_logs: PackedStringArray = []
var max_logs: int = 50

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

	var title = Label.new()
	title.text = "[CONSOLE] LOG"
	title.add_theme_color_override("font_color", Color(0.0, 1.0, 0.25))
	vbox.add_child(title)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	log_text = RichTextLabel.new()
	log_text.bbcode_enabled = true
	log_text.fit_content_height = true
	log_text.scroll_following = true
	log_text.anchor_right = 1.0
	log_text.anchor_bottom = 1.0
	vbox.add_child(log_text)

func _add_log(message: String):
	var colored = message
	if "ERROR" in message:
		colored = "[color=red]%s[/color]" % message
	elif "OK" in message or "success" in message:
		colored = "[color=lime]%s[/color]" % message
	elif "sync" in message or "SYNC" in message:
		colored = "[color=cyan]%s[/color]" % message
	elif "$" in message or "TREASURY" in message:
		colored = "[color=gold]%s[/color]" % message
	else:
		colored = "[color=white]%s[/color]" % message

	console_logs.append(colored)
	if console_logs.size() > max_logs:
		console_logs.remove_at(0)

	log_text.clear()
	for entry in console_logs:
		log_text.append_text(entry + "\n")

func _update():
	pass
