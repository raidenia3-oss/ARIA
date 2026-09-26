class_name ParticleSystem3D
extends GPUParticles3D

enum Mode { AURA, EXPLOSION, IMPLOSION, VORTEX, BEAM, STREAM, DOMAIN_EXPANSION }

@export var mode := Mode.AURA
@export var max_particles := 5000
@export var color_purple := Color("#7c4dff")
@export var color_cyan := Color("#00e5ff")
@export var color_cursed := Color("#8a2be2")
@export var color_red := Color("#ff4d4d")

var _current_mode := Mode.AURA
var _time := 0.0
var _domain_progress := 0.0


func _ready() -> void:
	amount = max_particles
	process_material = _create_process_material()
	_set_mode(mode)


func _process(delta: float) -> void:
	_time += delta


func set_mode(new_mode: Mode) -> void:
	_set_mode(new_mode)


func set_domain_expansion(active: bool) -> void:
	_set_mode(Mode.DOMAIN_EXPANSION if active else Mode.AURA)


func update_domain_progress(progress: float) -> void:
	_domain_progress = progress


func _set_mode(new_mode: Mode) -> void:
	_current_mode = new_mode
	if not process_material:
		return
	match new_mode:
		Mode.EXPLOSION:
			process_material.emission_shape = 1
			process_material.spread = 180.0
			process_material.gravity = Vector3(0, -9.8, 0)
			process_material.color = color_cyan
		Mode.IMPLOSION:
			process_material.emission_shape = 1
			process_material.spread = 360.0
			process_material.gravity = Vector3(0, 9.8, 0)
			process_material.color = color_red
		Mode.VORTEX:
			process_material.emission_shape = 2
			process_material.spread = 45.0
			process_material.color = color_cyan
		Mode.BEAM:
			process_material.emission_shape = 1
			process_material.spread = 5.0
			process_material.color = color_purple
		Mode.STREAM:
			process_material.emission_shape = 1
			process_material.spread = 90.0
			process_material.color = color_purple
		Mode.DOMAIN_EXPANSION:
			process_material.emission_shape = 1
			process_material.spread = 360.0
			process_material.gravity = Vector3(0, 0, 0)
			process_material.color = color_cursed
		Mode.AURA:
			process_material.emission_shape = 2
			process_material.spread = 120.0
			process_material.color = color_purple


func _create_process_material() -> ParticleProcessMaterial:
	var mat := ParticleProcessMaterial.new()
	mat.direction = Vector3(0, 1, 0)
	mat.spread = 120.0
	mat.flatness = 0.0
	mat.initial_velocity_min = 0.5
	mat.initial_velocity_max = 2.0
	mat.gravity = Vector3(0, -0.5, 0)
	mat.scale_min = 0.02
	mat.scale_max = 0.08
	mat.color = color_purple
	return mat
