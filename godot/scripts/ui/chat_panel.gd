extends Control
class_name ChatPanel

const JJKTheme = preload("res://scripts/ui/jjk_theme.gd")

signal send_message(prompt: String)
signal feedback(value: int)

@onready var message_list: VBoxContainer = $Margin/VBox/Scroll/MessageList
@onready var input: LineEdit = $Margin/VBox/InputRow/Input
@onready var send_btn: Button = $Margin/VBox/InputRow/Send
@onready var provider_label: Label = $Margin/VBox/ProviderRow/Provider
@onready var status_indicator: ColorRect = $Margin/VBox/ProviderRow/Status
@onready var clear_btn: Button = $Margin/VBox/ProviderRow/Clear

const HISTORY_PATH := "user://chat_history.json"
const MAX_HISTORY := 100

var _messages: Array[Dictionary] = []
var _streaming_message := false
var _current_stream_bubble: Panel
var _current_stream_label: RichTextLabel


func _ready() -> void:
	JJKTheme.apply_button(send_btn)
	send_btn.pressed.connect(_on_send_pressed)
	input.text_submitted.connect(_on_send_pressed)
	clear_btn.pressed.connect(clear_history)
	EventBus.chat_received.connect(_on_chat_received)
	EventBus.stream_token.connect(_on_stream_token)
	_load_history()
	if _messages.is_empty():
		_add_system_message("AURA lista. Escribe algo...")


func _on_send_pressed(_text: String = "") -> void:
	var prompt := input.text.strip_edges()
	if not prompt:
		return
	_add_user_message(prompt)
	input.clear()
	send_message.emit(prompt)


func _on_chat_received(prompt: String, text: String, provider: String) -> void:
	# Si estábamos en streaming de un mensaje, completarlo
	if _streaming_message and _current_stream_bubble:
		_finish_stream_message(text, provider)
	else:
		_add_assistant_message(text, provider)
	provider_label.text = "Proveedor: %s" % provider


func _on_stream_token(token: String, done: bool) -> void:
	if not _streaming_message:
		_start_stream_message()
	if not done:
		_current_stream_label.text += token
	else:
		var full_text := _current_stream_label.text
		_finish_stream_message(full_text, "local")


func _start_stream_message() -> void:
	_streaming_message = true
	var row := HBoxContainer.new()
	var bubble := Panel.new()
	JJKTheme.apply_panel(bubble)
	var style := bubble.get_theme_stylebox("panel").duplicate()
	style.bg_color = JJKTheme.PANEL
	row.alignment = BoxContainer.ALIGNMENT_BEGIN
	bubble.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bubble.custom_minimum_size = Vector2(200, 40)
	bubble.add_theme_stylebox_override("panel", style)
	_current_stream_label = RichTextLabel.new()
	_current_stream_label.fit_content = true
	_current_stream_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_current_stream_label.text = ""
	bubble.add_child(_current_stream_label)
	row.add_child(bubble)
	message_list.add_child(row)
	_current_stream_bubble = bubble


func _finish_stream_message(text: String, provider: String) -> void:
	if _current_stream_bubble:
		_messages.append({"role": "assistant", "text": text, "provider": provider})
		_save_history()
	_streaming_message = false
	_current_stream_bubble = null
	_current_stream_label = null


func _add_user_message(text: String) -> void:
	_messages.append({"role": "user", "text": text})
	_render_message(text, true)
	_save_history()


func _add_assistant_message(text: String, provider: String) -> void:
	_messages.append({"role": "assistant", "text": text, "provider": provider})
	_render_message(text, false, provider)
	_save_history()


func _add_system_message(text: String) -> void:
	_render_message(text, false, "system")


func _render_message(text: String, is_user: bool, provider: String = "") -> void:
	var row := HBoxContainer.new()
	var bubble := Panel.new()
	JJKTheme.apply_panel(bubble)
	var style := bubble.get_theme_stylebox("panel").duplicate()
	if is_user:
		style.bg_color = JJKTheme.ACCENT
		row.alignment = BoxContainer.ALIGNMENT_END
	else:
		style.bg_color = JJKTheme.PANEL
		row.alignment = BoxContainer.ALIGNMENT_BEGIN
	bubble.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bubble.custom_minimum_size = Vector2(200, 40)
	bubble.add_theme_stylebox_override("panel", style)
	var label := RichTextLabel.new()
	label.fit_content = true
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.scroll_following = true
	bubble.add_child(label)
	if not is_user and provider != "system":
		var feedback_row := HBoxContainer.new()
		var up := Button.new()
		var down := Button.new()
		up.text = "👍"
		down.text = "👎"
		up.pressed.connect(func(): feedback.emit(1))
		down.pressed.connect(func(): feedback.emit(-1))
		feedback_row.add_child(up)
		feedback_row.add_child(down)
		bubble.add_child(feedback_row)
	row.add_child(bubble)
	message_list.add_child(row)


func _load_history() -> void:
	if not FileAccess.file_exists(HISTORY_PATH):
		return
	var data := FileAccess.get_file_as_string(HISTORY_PATH)
	var parsed: Array = JSON.parse_string(data)
	if parsed is Array:
		for entry in parsed:
			var text = str(entry.get("text", ""))
			var role = str(entry.get("role", "system"))
			var provider = str(entry.get("provider", ""))
			_messages.append(entry)
			_render_message(text, role == "user", provider)


func _save_history() -> void:
	if _messages.size() > MAX_HISTORY:
		_messages = _messages.slice(-MAX_HISTORY)
	var file := FileAccess.open(HISTORY_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(_messages))


func clear_history() -> void:
	_messages.clear()
	for child in message_list.get_children():
		child.queue_free()
	if FileAccess.file_exists(HISTORY_PATH):
		DirAccess.remove_absolute(HISTORY_PATH)
	_add_system_message("Historial limpiado.")
