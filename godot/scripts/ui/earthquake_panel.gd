extends Control
class_name EarthquakePanel

@onready var timeline_list: VBoxContainer = $Margin/VBox/TimelineList
var eq_3d: Node3D

var _events: Array[Dictionary] = []


func _ready() -> void:
	eq_3d = $Eq3D if has_node("Eq3D") else null
	EventBus.earthquake_risk_update.connect(_on_earthquake_update)


func _on_earthquake_update(data: Dictionary) -> void:
	_events = data.get("events", [])
	_update_3d_visuals()
	_update_timeline()


func _update_3d_visuals() -> void:
	if not eq_3d:
		return
	for child in eq_3d.get_children():
		child.queue_free()

	for evt in _events:
		var magnitude := float(evt.get("magnitude", 0.0))
		var depth := float(evt.get("depth", 10.0))
		var pos := Vector3(
			(float(evt.get("lon", 0.0)) / 90.0) * 4.0,
			0.0,
			(float(evt.get("lat", 0.0)) / 90.0) * 2.0
		)
		var sphere := MeshInstance3D.new()
		var mesh := SphereMesh.new()
		mesh.radius = 0.05 + magnitude * 0.15
		mesh.height = mesh.radius * 2.0
		sphere.mesh = mesh
		sphere.position = pos

		var depth_ratio: float = clamp(depth / 300.0, 0.0, 1.0)
		var color := Color(1.0 - depth_ratio, 0.2, depth_ratio)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = color
		mat.emission_enabled = true
		mat.emission = color
		mat.emission_energy_multiplier = 0.3 + magnitude * 0.5
		sphere.material_override = mat
		eq_3d.add_child(sphere)


func _update_timeline() -> void:
	for child in timeline_list.get_children():
		child.queue_free()
	for evt in _events.slice(0, 10):
		var row := HBoxContainer.new()
		var label := Label.new()
		label.text = "M%s %s" % [evt.get("magnitude", "?"), evt.get("place", "?")]
		label.add_theme_color_override("font_color", Color("#ff4d4d"))
		row.add_child(label)
		timeline_list.add_child(row)
