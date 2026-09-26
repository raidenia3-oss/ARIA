extends Control
class_name LanguageSelector

var supported_languages: Array = []
var current_language: String = "en"
var language_dropdown: OptionButton

func _ready() -> void:
	_build_ui()
	_load_languages()

func _build_ui() -> void:
	var hbox = HBoxContainer.new()
	add_child(hbox)

	var label = Label.new()
	label.text = "Language: "
	hbox.add_child(label)

	language_dropdown = OptionButton.new()
	language_dropdown.item_selected.connect(_on_language_selected)
	hbox.add_child(language_dropdown)

func _load_languages() -> void:
	if AuraClient == null:
		return
	var result = AuraClient.request_json("GET", "/api/localization/languages")
	if result.is_empty():
		return
	supported_languages = result.get("languages", [])
	for lang in supported_languages:
		language_dropdown.add_item(lang.get("native_name", lang.get("code", "")))

func _on_language_selected(index: int) -> void:
	if index >= 0 and index < supported_languages.size():
		current_language = supported_languages[index]["code"]
		_apply_language()
		print("✅ Language changed to", current_language)

func _apply_language() -> void:
	if AuraClient:
		AuraClient.set_language(current_language)
	get_tree().call_group("language_aware", "on_language_changed", current_language)

func get_current_language() -> String:
	return current_language
