extends PanelContainer
class_name CyberpunkTerminal

signal command_submitted(command: String)

@onready var output: RichTextLabel = $Margin/VBox/Output
@onready var input: LineEdit = $Margin/VBox/InputRow/Input
@onready var send_btn: Button = $Margin/VBox/InputRow/Send
@onready var status_row: HBoxContainer = $Margin/VBox/StatusRow

var _history: Array[String] = []
var _history_index := -1
var _prompt_color := Color(0.0, 1.0, 0.5)
var _system_color := Color(0.5, 0.8, 1.0)
var _error_color := Color(1.0, 0.3, 0.3)
var _accent_color := Color(1.0, 0.8, 0.0)


func _ready() -> void:
	_apply_theme()
	input.text_submitted.connect(_on_input_submitted)
	send_btn.pressed.connect(_on_send_pressed)
	input.grab_focus()
	_print_system("AURA Cyberpunk Terminal v2.0")
	_print_system("Escribe 'help' para ver comandos disponibles.")


func _apply_theme() -> void:
	if output:
		output.clear()
		output.add_theme_color_override("default_color", Color(0.0, 1.0, 0.5))
		output.scroll_following = true
	if input:
		input.placeholder_text = ">"
	if send_btn:
		send_btn.text = "ENVIAR"
	var status_label := Label.new()
	status_label.text = "ONLINE"
	status_label.add_theme_color_override("font_color", Color(0.0, 1.0, 0.5))
	if status_row:
		status_row.add_child(status_label)


func _on_input_submitted(text: String) -> void:
	_execute_command(text)


func _on_send_pressed() -> void:
	var text := input.text.strip_edges()
	if not text:
		return
	input.clear()
	_execute_command(text)


func _execute_command(command: String) -> void:
	if command.is_empty():
		return
	_history.append(command)
	_history_index = _history.size()
	_print_prompt(command)
	command_submitted.emit(command)
	var parts := command.split(" ", false)
	var cmd := parts[0].to_lower()
	var args := parts.slice(1)
	match cmd:
		"help":
			_print_system("Comandos: help | status | brain | orchestrator | devices | wifi | telemetry | topology | clear")
		"status":
			_print_system("Estado del sistema: ONLINE")
		"brain":
			_print_system("Cerebro unificado activo. Usa /api/brain para estadísticas.")
		"orchestrator":
			_print_system("Orquestador de dispositivos activo. Usa /api/orchestrator para estado.")
		"devices":
			_print_system("Lista de dispositivos. Usa /api/agent/command con command=devices_list.")
		"wifi":
			_print_system("Escaneando redes Wi-Fi... Usa /api/wifi/scan.")
		"telemetry":
			_print_system("Obteniendo telemetría... Usa /api/system/telemetry.")
		"topology":
			_print_system("Mapeando red... Usa /api/network/topology.")
		"clear":
			if output:
				output.clear()
		_:
			_print_error("Comando desconocido: %s" % cmd)


func _print_prompt(text: String) -> void:
	if output:
		output.push_color(_prompt_color)
		output.append_text("> %s\n" % text)
		output.pop()
		output.scroll_to_line(output.get_line_count())


func _print_system(text: String) -> void:
	if output:
		output.push_color(_system_color)
		output.append_text("[SISTEMA] %s\n" % text)
		output.pop()
		output.scroll_to_line(output.get_line_count())


func _print_error(text: String) -> void:
	if output:
		output.push_color(_error_color)
		output.append_text("[ERROR] %s\n" % text)
		output.pop()
		output.scroll_to_line(output.get_line_count())


func append_log(service: String, level: String, message: String) -> void:
	if not output:
		return
	var color := Color(0.8, 0.8, 0.8)
	match level:
		"INFO":
			color = _system_color
		"ERROR":
			color = _error_color
		"WARNING":
			color = _accent_color
	output.push_color(color)
	output.append_text("[%s] [%s] %s\n" % [service, level, message])
	output.pop()
	output.scroll_to_line(output.get_line_count())
