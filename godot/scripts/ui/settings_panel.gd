extends Control
class_name SettingsPanel

const JJKTheme = preload("res://scripts/ui/jjk_theme.gd")

const SETTINGS_PATH := "user://settings.json"

@onready var backend_input: LineEdit = $Margin/VBox/BackendRow/BackendInput
@onready var theme_option: OptionButton = $Margin/VBox/ThemeRow/ThemeOption
@onready var voice_option: OptionButton = $Margin/VBox/VoiceRow/VoiceOption
@onready var save_btn: Button = $Margin/VBox/SaveBtn


func _ready() -> void:
	save_btn.pressed.connect(_save)
	_load_settings()


func _load_settings() -> void:
	if not FileAccess.file_exists(SETTINGS_PATH):
		return
	var data := FileAccess.get_file_as_string(SETTINGS_PATH)
	var parsed := JSON.parse_string(data)
	if parsed is Dictionary:
		if parsed.has("backend_url"):
			backend_input.text = parsed.backend_url
		if parsed.has("theme"):
			theme_option.select(0 if parsed.theme == "jjk" else 1)
		if parsed.has("voice"):
			voice_option.select(0 if parsed.voice == "piper" else 1)


func _save() -> void:
	var settings := {
		"backend_url": backend_input.text.strip_edges(),
		"theme": "jjk" if theme_option.selected == 0 else "classic",
		"voice": "piper" if voice_option.selected == 0 else "silent",
	}
	var file := FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(settings))
	JJKTheme.show_toast("Configuración guardada")
