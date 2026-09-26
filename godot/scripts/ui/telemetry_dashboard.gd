extends PanelContainer
class_name TelemetryDashboard

signal refresh_requested()

@onready var cpu_bar: ProgressBar = $Margin/VBox/CPURow/CPU
@onready var cpu_label: Label = $Margin/VBox/CPURow/Label
@onready var mem_bar: ProgressBar = $Margin/VBox/MemRow/Memory
@onready var mem_label: Label = $Margin/VBox/MemRow/Label
@onready var disk_bar: ProgressBar = $Margin/VBox/DiskRow/Disk
@onready var disk_label: Label = $Margin/VBox/DiskRow/Label
@onready var net_label: Label = $Margin/VBox/NetRow/Label
@onready var proc_list: VBoxContainer = $Margin/VBox/ProcessList

var _timer: Timer
var _last_net := {"bytes_sent": 0, "bytes_recv": 0}


func _ready() -> void:
	_timer = Timer.new()
	_timer.wait_time = 1.0
	_timer.timeout.connect(_refresh)
	add_child(_timer)
	_timer.start()
	_apply_theme()


func _apply_theme() -> void:
	for bar in [cpu_bar, mem_bar, disk_bar]:
		if bar:
			bar.min_value = 0.0
			bar.max_value = 100.0
			bar.value = 0.0
	_refresh()


func _refresh() -> void:
	refresh_requested.emit()
	if not AuraClient or not AuraClient.has_method("get_telemetry"):
		return
	var data := AuraClient.get_telemetry()
	if not data or not data is Dictionary:
		return
	_update_cpu(float(data.get("cpu", 0.0)))
	_update_memory(float(data.get("memory", 0.0)))
	_update_disk(float(data.get("disk", 0.0)))
	_update_network(data.get("network", {}))
	_update_processes(data.get("processes", []))


func _update_cpu(value: float) -> void:
	if cpu_bar:
		cpu_bar.value = value
	if cpu_label:
		cpu_label.text = "CPU: %.1f%%" % value


func _update_memory(value: float) -> void:
	if mem_bar:
		mem_bar.value = value
	if mem_label:
		mem_label.text = "RAM: %.1f%%" % value


func _update_disk(value: float) -> void:
	if disk_bar:
		disk_bar.value = value
	if disk_label:
		disk_label.text = "DISCO: %.1f%%" % value


func _update_network(net: Dictionary) -> void:
	if not net_label:
		return
	var sent := net.get("bytes_sent", 0)
	var recv := net.get("bytes_recv", 0)
	var delta_sent := max(0.0, float(sent - _last_net.bytes_sent))
		var delta_recv := max(0.0, float(recv - _last_net.bytes_recv))
	_last_net = {"bytes_sent": sent, "bytes_recv": recv}
	net_label.text = "⬆ %.1f KB/s ⬇ %.1f KB/s" % [delta_sent / 1024.0, delta_recv / 1024.0]


func _update_processes(processes: Array) -> void:
	if not proc_list:
		return
	for child in proc_list.get_children():
		child.queue_free()
	for proc in processes.slice(0, 8):
		var row := HBoxContainer.new()
		var name := Label.new()
		name.text = str(proc.get("name", ""))
		name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var cpu := Label.new()
		cpu.text = "%.1f%%" % float(proc.get("cpu_percent", 0.0) or 0.0)
		var mem := Label.new()
		mem.text = "%.1f%%" % float(proc.get("memory_percent", 0.0) or 0.0)
		row.add_child(name)
		row.add_child(cpu)
		row.add_child(mem)
		proc_list.add_child(row)
