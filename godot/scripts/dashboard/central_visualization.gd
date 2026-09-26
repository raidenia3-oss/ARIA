extends Control

var particles: GPUParticles2D
var center_label: Label
var sync_percent_label: Label
var rotation_speed: float = 0.3
var current_rotation: float = 0.0

func _ready() -> void:
	_build_ui()

func _build_ui() -> void:
	var bg = ColorRect.new()
	bg.color = Color(0.02, 0.02, 0.04, 0.9)
	bg.anchor_right = 1.0
	bg.anchor_bottom = 1.0
	add_child(bg)

	particles = GPUParticles2D.new()
	particles.position = size / 2.0
	particles.amount = 60
	particles.lifetime = 2.5
	particles.emitting = true
	add_child(particles)

	center_label = Label.new()
	center_label.text = "AURA"
	center_label.anchor_left = 0.5
	center_label.anchor_top = 0.5
	center_label.offset_left = -30
	center_label.offset_top = -12
	center_label.add_theme_color_override("font_color", Color(0.54, 0.17, 0.89))
	center_label.add_theme_font_size_override("font_size", 32)
	add_child(center_label)

	sync_percent_label = Label.new()
	sync_percent_label.text = "SYNC: --"
	sync_percent_label.anchor_left = 0.5
	sync_percent_label.anchor_top = 0.5
	sync_percent_label.offset_top = 24
	sync_percent_label.offset_left = -28
	add_child(sync_percent_label)

func _process(delta: float) -> void:
	current_rotation += rotation_speed * delta
	rotation = current_rotation

func _update() -> void:
	pass
