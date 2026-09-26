extends Node2D
class_name GestureParticleSystem

signal particle_triggered(gesture: String, position: Vector2)

@onready var particles_fist: GPUParticles2D = $Fist
@onready var particles_index: GPUParticles2D = $Index
@onready var particles_peace: GPUParticles2D = $Peace
@onready var particles_open_hand: GPUParticles2D = $OpenHand
@onready var particles_swipe: GPUParticles2D = $Swipe
@onready var particles_heart: GPUParticles2D = $Heart

var _gesture_colors := {
	"fist": Color("#ff4d4d"),
	"index": Color("#00e5ff"),
	"peace": Color("#00e676"),
	"open_hand": Color("#ffea00"),
	"swipe": Color("#ff9800"),
	"heart": Color("#e040fb"),
}


func _ready() -> void:
	_setup_particles()


func _setup_particles() -> void:
	for child in get_children():
		if child is GPUParticles2D:
			child.emitting = false
			child.one_shot = true
			child.explosiveness = 0.8
			child.process_material = _create_material(child.name)


func _create_material(gesture_name: String) -> ParticleProcessMaterial:
	var mat := ParticleProcessMaterial.new()
	var color: Color = _gesture_colors.get(gesture_name.to_lower(), Color.WHITE)
	mat.direction = Vector3(0, -1, 0)
	mat.spread = 180.0
	mat.initial_velocity_min = 100.0
	mat.initial_velocity_max = 300.0
	mat.gravity = Vector3(0, 200.0, 0)
	mat.scale_min = 0.02
	mat.scale_max = 0.08
	mat.color = color
	return mat


func trigger_gesture(gesture: String, position: Vector2 = Vector2.ZERO) -> void:
	var gesture_key := gesture.to_lower()
	if not _gesture_colors.has(gesture_key):
		return
	
	particle_triggered.emit(gesture, position)
	
	var particles: GPUParticles2D = _get_particle_node(gesture_key)
	if particles:
		particles.global_position = position
		particles.restart()
		particles.emitting = true


func _get_particle_node(gesture: String) -> GPUParticles2D:
	match gesture:
		"fist":
			return particles_fist
		"index":
			return particles_index
		"peace":
			return particles_peace
		"open_hand":
			return particles_open_hand
		"swipe":
			return particles_swipe
		"heart":
			return particles_heart
		_:
			return null
