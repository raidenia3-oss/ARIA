extends Control
class_name SyncPanel

@onready var url_input: LineEdit = $Margin/VBox/UrlInput
@onready var device_input: LineEdit = $Margin/VBox/DeviceInput
@onready var connect_btn: Button = $Margin/VBox/ConnectBtn
@onready var sync_btn: Button = $Margin/VBox/SyncBtn
@onready var status_label: Label = $Margin/VBox/StatusLabel
@onready var devices_list: VBoxContainer = $Margin/VBox/DevicesList

var _client: AuraClient
var _current_url: String = ""


func _ready() -> void:
	_client = get_node("/root/AuraClient") as AuraClient
	if not _client:
		_client = get_tree().root.get_node_or_null("AuraClient")
	if not _client:
		push_error("[SyncPanel] AuraClient not found")
		return
	connect_btn.pressed.connect(_on_connect_pressed)
	sync_btn.pressed.connect(_on_sync_pressed)
	url_input.text = _client.get_backend_url()
	device_input.text = "godot-mobile-%s" % str(randi() % 9999)
	status_label.text = "Sync ready"
	_refresh_devices_timer()


func _on_connect_pressed() -> void:
	var url := url_input.text.strip_edges()
	if url.is_empty():
		status_label.text = "URL vacia"
		return
	_current_url = url
	_client.set_backend_url(url)
	status_label.text = "Conectando a %s..." % url
	var ok := _client._probe_backend(url)
	if ok:
		status_label.text = "Conectado: %s" % url
		var device_id := device_input.text.strip_edges()
		var role := "mobile" if _client.is_using_local() == false else "pc"
		_client.init_sync(device_id, role)
		_client.start_sync()
	else:
		status_label.text = "Falló conexión a %s" % url


func _on_sync_pressed() -> void:
	if not _client:
		return
	_client._tick_sync.call()
	var devices := _client.get_sync_devices()
	_render_devices(devices)
	status_label.text = "Sync actualizado (%d)" % devices.size()


func _refresh_devices_timer() -> void:
	var timer := Timer.new()
	timer.wait_time = 3.0
	timer.timeout.connect(_on_sync_pressed)
	add_child(timer)
	timer.start()


func _render_devices(devices: Dictionary) -> void:
	for child in devices_list.get_children():
		child.queue_free()
	for device_id in devices:
		var info := devices[device_id] as Dictionary
		var row := HBoxContainer.new()
		var label := Label.new()
		label.text = "%s | %s | %s" % [
			str(device_id),
			str(info.get("role", "?")),
			str(info.get("state", {}).get("connected", false)),
		]
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		var cmd_btn := Button.new()
		cmd_btn.text = "CMD"
		cmd_btn.pressed.connect(_send_test_command.bind(device_id))
		row.add_child(cmd_btn)
		devices_list.add_child(row)


func _send_test_command(device_id: String) -> void:
	var res := _client.send_sync_command(device_id, "ping", {"from": _client._sync_device_id})
	status_label.text = "CMD -> %s : %s" % [device_id, str(res)]
