extends PanelContainer
class_name NexusHUD

signal hud_ready()

@onready var intel_panel: PanelContainer = $Margin/VBox/IntelPanel
@onready var audio_panel: PanelContainer = $Margin/VBox/AudioPanel
@onready var system_panel: PanelContainer = $Margin/VBox/SystemPanel

@onready var gesture_label: Label = $Margin/VBox/IntelPanel/VBox/GestureLabel
@onready var conf_label: Label = $Margin/VBox/IntelPanel/VBox/ConfLabel
@onready var freq_label: Label = $Margin/VBox/AudioPanel/VBox/FreqLabel
@onready var level_label: Label = $Margin/VBox/AudioPanel/VBox/LevelLabel
@onready var cpu_bar: ProgressBar = $Margin/VBox/SystemPanel/VBox/CPURow/CPU
@onready var cpu_label: Label = $Margin/VBox/SystemPanel/VBox/CPURow/Label
@onready var ram_bar: ProgressBar = $Margin/VBox/SystemPanel/VBox/RAMRow/RAM
@onready var ram_label: Label = $Margin/VBox/SystemPanel/VBox/RAMRow/Label
@onready var disk_bar: ProgressBar = $Margin/VBox/SystemPanel/VBox/DISKRow/DISK
@onready var disk_label: Label = $Margin/VBox/SystemPanel/VBox/DISKRow/Label
@onready var net_label: Label = $Margin/VBox/SystemPanel/VBox/NetRow/Label

var _telemetry_timer: Timer
var _current_gesture := "idle"
var _current_conf := 0.0
var _audio_level := -60.0


func _ready() -> void:
	_apply_theme()
	if EventBus:
		EventBus.gesture_detected.connect(_on_gesture_detected)
	_telemetry_timer = Timer.new()
	_telemetry_timer.wait_time = 1.0
	_telemetry_timer.timeout.connect(_refresh_telemetry)
	add_child(_telemetry_timer)
	_telemetry_timer.start()
	_refresh_telemetry()
	hud_ready.emit()


func _apply_theme() -> void:
	var accent := Color("#38bdf8")
	var cursed := Color("#8a2be2")
	var bg := Color("#0f172a")
	var panel_style := StyleBoxFlat.new()
	panel_style.bg_color = bg
	panel_style.border_color = accent
	panel_style.border_width_left = 1
	panel_style.border_width_right = 1
	panel_style.border_width_top = 1
	panel_style.border_width_bottom = 1
	panel_style.corner_radius_top_left = 4
	panel_style.corner_radius_top_right = 4
	panel_style.corner_radius_bottom_left = 4
	panel_style.corner_radius_bottom_right = 4
	for panel in [intel_panel, audio_panel, system_panel]:
		if panel:
			panel.add_theme_stylebox_override("panel", panel_style)
			var title := Label.new()
			title.text = "INTEL" if panel == intel_panel else ("AUDIO" if panel == audio_panel else "SYSTEM")
			title.add_theme_color_override("font_color", cursed if panel == intel_panel else accent)
			title.add_theme_font_size_override("font_size", 14)
			var vbox: VBoxContainer = panel.get_node("VBox") if panel.has_node("VBox") else null
			if vbox:
				vbox.add_child(title)
	if gesture_label:
		gesture_label.text = "GESTURE: idle"
	if conf_label:
		conf_label.text = "CONF: 0%"
	if freq_label:
		freq_label.text = "FREQUENCY: -- Hz"
	if level_label:
		level_label.text = "LEVEL: -∞ dB"
	if cpu_bar:
		cpu_bar.min_value = 0.0
		cpu_bar.max_value = 100.0
	if ram_bar:
		ram_bar.min_value = 0.0
		ram_bar.max_value = 100.0
	if disk_bar:
		disk_bar.min_value = 0.0
		disk_bar.max_value = 100.0


func _on_gesture_detected(gesture: String, confidence: float, fingers: int) -> void:
	_current_gesture = gesture
	_current_conf = confidence
	if gesture_label:
		gesture_label.text = "GESTURE: %s" % gesture.to_upper()
	if conf_label:
		conf_label.text = "CONF: %.0f%%" % (confidence * 100.0)
	_audio_level = -60.0 + confidence * 60.0
	if freq_label:
		freq_label.text = "FREQUENCY: %.0f Hz" % (200 + confidence * 1800.0)
	if level_label:
		level_label.text = "LEVEL: %.1f dB" % _audio_level


func _refresh_telemetry() -> void:
	if not AuraClient or not AuraClient.has_method("get_telemetry"):
		return
	var data: Dictionary = AuraClient.get_telemetry()
	if not data:
		return
	if cpu_bar:
		cpu_bar.value = float(data.get("cpu", 0.0))
	if cpu_label:
		cpu_label.text = "CPU: %.1f%%" % float(data.get("cpu", 0.0))
	if ram_bar:
		ram_bar.value = float(data.get("memory", 0.0))
	if ram_label:
		ram_label.text = "RAM: %.1f%%" % float(data.get("memory", 0.0))
	if disk_bar:
		disk_bar.value = float(data.get("disk", 0.0))
	if disk_label:
		disk_label.text = "DISK: %.1f%%" % float(data.get("disk", 0.0))
	var net: Dictionary = data.get("network", {})
	if net_label:
		var sent := float(net.get("bytes_sent", 0.0))
		var recv := float(net.get("bytes_recv", 0.0))
		net_label.text = "NET: ↑%.1f ↓%.1f KB/s" % [sent / 1024.0, recv / 1024.0]
