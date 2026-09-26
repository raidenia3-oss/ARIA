extends Control
class_name NarrativePanel

var story_title_input: LineEdit
var premise_input: TextEdit
var tone_selector: OptionButton
var characters_input: TextEdit
var story_text: RichTextLabel
var prompt_input: LineEdit
var send_button: Button
var create_button: Button

var current_story_id: int = -1
var is_streaming: bool = false

func _ready() -> void:
	_build_ui()

func _build_ui() -> void:
	var scroll = ScrollContainer.new()
	scroll.anchor_right = 1.0
	scroll.anchor_bottom = 1.0
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroll)

	var vbox = VBoxContainer.new()
	vbox.anchor_right = 1.0
	vbox.anchor_bottom = 1.0
	vbox.offset_left = 10
	vbox.offset_top = 10
	vbox.offset_right = -10
	vbox.offset_bottom = -10
	scroll.add_child(vbox)

	var title = Label.new()
	title.text = "NARRATIVE ENGINE"
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color(0.54, 0.17, 0.89))
	vbox.add_child(title)

	story_title_input = LineEdit.new()
	story_title_input.placeholder_text = "Título de la historia"
	story_title_input.custom_minimum_size = Vector2(0, 28)
	vbox.add_child(story_title_input)

	premise_input = TextEdit.new()
	premise_input.placeholder_text = "Premisa / escenario base..."
	premise_input.custom_minimum_size = Vector2(0, 70)
	vbox.add_child(premise_input)

	tone_selector = OptionButton.new()
	tone_selector.add_item("Dramático", 0)
	tone_selector.add_item("Oscuro", 1)
	tone_selector.add_item("Romántico", 2)
	tone_selector.add_item("Noir", 3)
	tone_selector.add_item("Whimsical", 4)
	vbox.add_child(tone_selector)

	characters_input = TextEdit.new()
	characters_input.text = '{"Sukuna": {"traits": ["proud", "powerful"]}, "Yuji": {"traits": ["determined"]}}'
	characters_input.custom_minimum_size = Vector2(0, 80)
	vbox.add_child(characters_input)

	create_button = Button.new()
	create_button.text = "Crear historia"
	create_button.pressed.connect(_on_create_story)
	vbox.add_child(create_button)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	var writing = Label.new()
	writing.text = "Escritura"
	writing.add_theme_font_size_override("font_size", 20)
	vbox.add_child(writing)

	story_text = RichTextLabel.new()
	story_text.bbcode_enabled = true
	story_text.custom_minimum_size = Vector2(0, 260)
	story_text.scroll_following = true
	story_text.anchor_right = 1.0
	vbox.add_child(story_text)

	prompt_input = LineEdit.new()
	prompt_input.placeholder_text = "Continúa la historia..."
	prompt_input.custom_minimum_size = Vector2(0, 28)
	vbox.add_child(prompt_input)

	send_button = Button.new()
	send_button.text = "Generar siguiente escena"
	send_button.pressed.connect(_on_generate_scene)
	vbox.add_child(send_button)

func _on_create_story() -> void:
	var title = story_title_input.text.strip_edges()
	var premise = premise_input.text.strip_edges()
	if title.is_empty() or premise.is_empty():
		print("Narrative: título y premisa requeridos")
		return
	var characters = JSON.parse_string(characters_input.text)
	if not characters or not characters is Dictionary:
		print("Narrative: personajes inválidos")
		return
	var tone = tone_selector.get_item_text(tone_selector.selected).to_lower()

	var payload = {
		"title": title,
		"premise": premise,
		"characters": characters,
		"tone": tone,
	}
	var response = _post_json("/api/narrative/stories/create", payload)
	if response.is_empty():
		print("Narrative: error creando historia")
		return
	current_story_id = int(response.get("story_id", -1))
	story_text.clear()
	story_text.append_text("[b]%s[/b]\n\n%s\n\n" % [title, premise])
	print("Narrative: historia creada %s" % current_story_id)

func _on_generate_scene() -> void:
	if current_story_id < 0:
		print("Narrative: crea una historia primero")
		return
	var prompt = prompt_input.text.strip_edges()
	if prompt.is_empty():
		print("Narrative: prompt vacío")
		return
	is_streaming = true
	send_button.disabled = true
	var response = _post_json("/api/narrative/stories/continue", {
		"story_id": current_story_id,
		"prompt": prompt,
	})
	if not response.is_empty():
		story_text.append_text("\n" + str(response.get("text", "")) + "\n")
		prompt_input.clear()
	else:
		print("Narrative: error generando escena")
	is_streaming = false
	send_button.disabled = false

func _post_json(endpoint: String, payload: Dictionary) -> Dictionary:
	var client = HTTPClient.new()
	var url = "http://127.0.0.1:8000"
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
		if Time.get_ticks_msec() - start > 60000:
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
