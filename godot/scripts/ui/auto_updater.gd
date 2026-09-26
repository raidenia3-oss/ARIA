extends Control
class_name AutoUpdater

enum UpdateStatus {
	IDLE,
	CHECKING,
	UPDATE_AVAILABLE,
	DOWNLOADING,
	INSTALLING,
	ROLLBACK,
	ERROR
}

var current_status: UpdateStatus = UpdateStatus.IDLE
var current_version: String = "3.1.0"
var update_url: String = ""
var downloaded_patch: String = ""

var status_label: Label
var progress_bar: ProgressBar
var update_button: Button
var changelog_text: RichTextLabel

func _ready() -> void:
	_build_ui()
	_load_version_file()

func _build_ui() -> void:
	var vbox = VBoxContainer.new()
	add_child(vbox)

	var title = Label.new()
	title.text = "[AUTO-UPDATE]"
	title.add_theme_font_size_override("font_size", 18)
	vbox.add_child(title)

	status_label = Label.new()
	status_label.text = "Status: IDLE"
	vbox.add_child(status_label)

	progress_bar = ProgressBar.new()
	progress_bar.value = 0
	progress_bar.custom_minimum_size = Vector2(0, 18)
	vbox.add_child(progress_bar)

	var changelog_label = Label.new()
	changelog_label.text = "Changelog:"
	vbox.add_child(changelog_label)

	changelog_text = RichTextLabel.new()
	changelog_text.bbcode_enabled = true
	changelog_text.custom_minimum_size = Vector2(0, 100)
	vbox.add_child(changelog_text)

	var button_hbox = HBoxContainer.new()
	vbox.add_child(button_hbox)

	var check_btn = Button.new()
	check_btn.text = "Check for Updates"
	check_btn.pressed.connect(_on_check_updates)
	button_hbox.add_child(check_btn)

	update_button = Button.new()
	update_button.text = "Update Now"
	update_button.disabled = true
	update_button.pressed.connect(_on_update_pressed)
	button_hbox.add_child(update_button)

	var rollback_btn = Button.new()
	rollback_btn.text = "Rollback"
	rollback_btn.pressed.connect(_on_rollback_pressed)
	button_hbox.add_child(rollback_btn)

func _load_version_file() -> void:
	var version_file = "res://local_version.json"
	if ResourceLoader.exists(version_file):
		var content = FileAccess.get_file_as_string(version_file)
		var json = JSON.new()
		var data = json.parse_string(content)
		if data:
			current_version = str(data.get("version", "3.1.0"))
			print("AutoUpdater: versión local %s" % current_version)

func _on_check_updates() -> void:
	check_for_updates()

func check_for_updates() -> void:
	_set_status(UpdateStatus.CHECKING, "Checking for updates...")
	var result = _post_json("/api/updates/check?client_version=%s" % current_version, {})
	if result.is_empty():
		_set_status(UpdateStatus.ERROR, "Failed to check updates")
		return
	if result.get("update_available", false):
		_handle_update_available(result)
	else:
		_set_status(UpdateStatus.IDLE, "You are up to date!")
		status_label.text = "Latest: %s" % result.get("latest_version", "")

func _handle_update_available(update_info: Dictionary) -> void:
	_set_status(UpdateStatus.UPDATE_AVAILABLE, "Update available: %s" % update_info.get("latest_version", ""))
	update_button.disabled = false
	var changelog = update_info.get("changelog", "")
	changelog_text.clear()
	changelog_text.append_text(str(changelog))
	update_url = "/api/updates/download/%s" % update_info.get("latest_version", "")
	print("AutoUpdater: actualización disponible %s" % update_info.get("latest_version", ""))

func _on_update_pressed() -> void:
	if update_url.is_empty():
		status_label.text = "Error: No update URL"
		return
	_download_patch()

func _download_patch() -> void:
	_set_status(UpdateStatus.DOWNLOADING, "Downloading update...")
	for i in range(0, 101, 5):
		progress_bar.value = i
		await get_tree().create_timer(0.05).timeout
	downloaded_patch = "update_patch_%s.zip" % current_version
	_install_patch()

func _install_patch() -> void:
	_set_status(UpdateStatus.INSTALLING, "Installing update...")
	for i in range(0, 101, 10):
		progress_bar.value = i
		await get_tree().create_timer(0.03).timeout
	var new_version = "3.1.1"
	var result = _post_json("/api/updates/installed/%s" % new_version, {})
	if result.get("status") == "confirmed":
		current_version = new_version
		_save_version_file()
		_set_status(UpdateStatus.IDLE, "Updated to v%s. Restart app for full effect." % new_version)
		update_button.disabled = true
		progress_bar.value = 100
	else:
		_set_status(UpdateStatus.ERROR, "Failed to confirm update")

func _on_rollback_pressed() -> void:
	_set_status(UpdateStatus.ROLLBACK, "Rolling back to previous version...")
	var previous_version = "3.1.0"
	var result = _post_json("/api/updates/rollback/%s" % previous_version, {})
	if result.get("status") == "success":
		current_version = previous_version
		_save_version_file()
		_set_status(UpdateStatus.IDLE, "Rollback to v%s successful" % previous_version)
		update_button.disabled = false
	else:
		_set_status(UpdateStatus.ERROR, "Rollback failed")

func _save_version_file() -> void:
	var version_data = {
		"version": current_version,
		"updated_at": Time.get_ticks_msec(),
		"installed_patches": [],
	}
	var json = JSON.stringify(version_data)
	var file = FileAccess.open("res://local_version.json", FileAccess.WRITE)
	if file:
		file.store_string(json)
		print("AutoUpdater: versión guardada %s" % current_version)

func _set_status(status: UpdateStatus, message: String) -> void:
	current_status = status
	status_label.text = "Status: %s - %s" % [UpdateStatus.keys()[status], message]
	match status:
		UpdateStatus.UPDATE_AVAILABLE:
			status_label.add_theme_color_override("font_color", Color.YELLOW)
		UpdateStatus.DOWNLOADING, UpdateStatus.INSTALLING:
			status_label.add_theme_color_override("font_color", Color.CYAN)
		UpdateStatus.ERROR:
			status_label.add_theme_color_override("font_color", Color.RED)
		UpdateStatus.IDLE:
			status_label.add_theme_color_override("font_color", Color.WHITE)

func _post_json(endpoint: String, payload: Dictionary) -> Dictionary:
	var client = HTTPClient.new()
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

func get_status_info() -> Dictionary:
	return {
		"current_version": current_version,
		"status": UpdateStatus.keys()[current_status],
		"update_available": current_status == UpdateStatus.UPDATE_AVAILABLE,
	}
