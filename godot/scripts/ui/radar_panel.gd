


extends Control
class_name RadarPanel

@onready var network_list: VBoxContainer = $Margin/VBox/NetworkList
var radar_3d: Node3D

var _networks: Array[Dictionary] = []


func _ready() -> void:
	radar_3d = $Radar3D if has_node("Radar3D") else null
	EventBus.wifi_update.connect(_on_wifi_update)


func _on_wifi_update(networks: Array, zones: Array, motion: Array, anomalies: Array) -> void:
	_networks = networks
	_update_3d_radar()
	_update_list()


func _update_3d_radar() -> void:
	if not radar_3d:
		return
	for child in radar_3d.get_children():
		child.queue_free()

	for net in _networks:
		var intensity := float(net.get("intensity", 0.0))
		var ssid := str(net.get("ssid", "unknown"))
		var pos := Vector3(
			randf_range(-2.0, 2.0),
			0.0,
			-2.0
		)
		var sphere := MeshInstance3D.new()
		var mesh := SphereMesh.new()
		mesh.radius = 0.05 + intensity * 0.15
		mesh.height = mesh.radius * 2.0
		sphere.mesh = mesh
		sphere.position = pos
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.0, 0.898, 1.0, 0.3 + intensity * 0.7)
		mat.emission_enabled = true
		mat.emission = Color(0.0, 0.898, 1.0)
		mat.emission_energy_multiplier = 0.5 + intensity * 2.0
		sphere.material_override = mat
		radar_3d.add_child(sphere)


func _update_list() -> void:
	for child in network_list.get_children():
		child.queue_free()
	for net in _networks:
		var row := HBoxContainer.new()
		var label := Label.new()
		label.text = "%s  (%.0f%%)" % [net.get("ssid", "?"), float(net.get("intensity", 0.0)) * 100.0]
		label.add_theme_color_override("font_color", Color("#00e5ff"))
		row.add_child(label)
		network_list.add_child(row)
