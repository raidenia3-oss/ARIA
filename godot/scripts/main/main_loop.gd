extends Node3D
class_name MainLoopController

@onready var chat_ui: Control = $CanvasLayer/ChatUI
@onready var radar_ui: Control = $CanvasLayer/RadarUI
@onready var earthquake_ui: Control = $CanvasLayer/EarthquakeUI
@onready var particle_system: GPUParticles3D = $World3D/ParticleWorld/GPUParticles3D
@onready var gesture_particles: Node2D = $CanvasLayer/GestureParticleSystem
@onready var nexus_hud: PanelContainer = $CanvasLayer/NexusHUD
@onready var btn_chat: Button = $CanvasLayer/ModeButtons/BtnChat
@onready var btn_radar: Button = $CanvasLayer/ModeButtons/BtnRadar
@onready var btn_eq: Button = $CanvasLayer/ModeButtons/BtnEq

var _mode := "chat"


func _ready() -> void:
	_set_mode("chat")
	btn_chat.pressed.connect(func(): _set_mode("chat"))
	btn_radar.pressed.connect(func(): _set_mode("radar"))
	btn_eq.pressed.connect(func(): _set_mode("earthquake"))
	if EventBus:
		EventBus.gesture_detected.connect(_on_gesture_detected)
	if nexus_hud and nexus_hud.has_method("_on_gesture_detected"):
		EventBus.gesture_detected.connect(nexus_hud._on_gesture_detected)


func _set_mode(mode: String) -> void:
	_mode = mode
	chat_ui.visible = mode == "chat"
	radar_ui.visible = mode == "radar"
	earthquake_ui.visible = mode == "earthquake"
	if particle_system and particle_system.has_method("set_mode"):
		if mode == "chat":
			particle_system.set_mode(0)
		elif mode == "radar":
			particle_system.set_mode(2)
		elif mode == "earthquake":
			particle_system.set_mode(1)
		else:
			particle_system.set_mode(0)


func _on_gesture_detected(gesture: String, confidence: float, fingers: int) -> void:
	if not gesture_particles:
		return
	var viewport: Viewport = get_viewport()
	if not viewport:
		return
	var viewport_size: Vector2 = viewport.get_visible_rect().size
	var center := Vector2(viewport_size.x * 0.5, viewport_size.y * 0.5)
	if gesture_particles.has_method("trigger_gesture"):
		gesture_particles.trigger_gesture(gesture, center)
