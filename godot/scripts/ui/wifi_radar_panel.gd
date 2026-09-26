extends PanelContainer
class_name WiFiRadarPanel

signal refresh_requested()

@onready var list: VBoxContainer = $Margin/VBox/Scroll/NetworkList
@onready var scan_btn: Button = $Margin/VBox/ScanRow/ScanButton
@onready var status_label: Label = $Margin/VBox/ScanRow/Status

var _timer: Timer
var _networks: Array[Dictionary] = []


func _ready() -> void:
	scan_btn.pressed.connect(_scan)
	_timer = Timer.new()
	_timer.wait_time = 10.0
	_timer.timeout.connect(_scan)
	add_child(_timer)
	_timer.start()
	_scan()


func _scan() -> void:
	refresh_requested.emit()
	if status_label:
		status_label.text = "ESCANEANDO..."
	if not AuraClient or not AuraClient.has_method("scan_wifi"):
		_status_done("NO DISPONIBLE")
		return
	var result := AuraClient.scan_wifi()
	if not result or not result is Dictionary:
		_status_done("ERROR")
		return
	_networks = result.get("networks", [])
	_render_list()
	_status_done("%d REDES" % _networks.size())


func _render_list() -> void:
	for child in list.get_children():
		child.queue_free()
	for net in _networks:
		var row := HBoxContainer.new()
		var ssid := Label.new()
		ssid.text = str(net.get("ssid", "???"))
		ssid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var signal_lbl := Label.new()
		signal_lbl.text = str(net.get("signal", "-"))
		var channel := Label.new()
		channel.text = str(net.get("channel", "-"))
		var bssid := Label.new()
		bssid.text = str(net.get("bssid", "-"))
		row.add_child(ssid)
		row.add_child(signal_lbl)
		row.add_child(channel)
		row.add_child(bssid)
		list.add_child(row)


func _status_done(text: String) -> void:
	if status_label:
		status_label.text = text
