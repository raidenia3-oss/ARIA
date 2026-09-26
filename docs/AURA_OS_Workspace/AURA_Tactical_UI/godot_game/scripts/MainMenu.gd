## MainMenu.gd — Pantalla de inicio con estado AURA, stats del héroe y botón Jugar
## Muestra indicador verde/rojo de conexión AURA y botón de sincronización

extends Control

@onready var connection_label: Label = $VBoxContainer/ConnectionLabel
@onready var level_label: Label = $VBoxContainer/LevelLabel
@onready var xp_label: Label = $VBoxContainer/XPLabel
@onready var gold_label: Label = $VBoxContainer/GoldLabel
@onready var play_button: Button = $VBoxContainer/PlayButton
@onready var sync_button: Button = $VBoxContainer/SyncButton
@onready var status_dot: ColorRect = $VBoxContainer/ConnectionInfo/StatusDot

func _ready() -> void:
	play_button.pressed.connect(_on_play_pressed)
	sync_button.pressed.connect(_on_sync_pressed)
	AURABridge.aura_connection_changed.connect(_on_aura_connected)
	_refresh_ui()
	print("[MainMenu] Pantalla de inicio cargada")

func _refresh_ui() -> void:
	level_label.text = "Nivel: %d" % GameState.level
	xp_label.text = "XP: %d/%d" % [GameState.xp, GameState.xp_to_next]
	gold_label.text = "Gold: %d" % GameState.gold
	var connected = AURABridge.is_connected_to_aura()
	status_dot.color = Color.GREEN if connected else Color.RED
	connection_label.text = "AURA: %s" % ("Online" if connected else "Offline")

func _on_play_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/GameWorld.tscn")

func _on_sync_pressed() -> void:
	AURABridge.sync_hero_data(GameState.get_save_data())
	connection_label.text = "Sincronizando..."
	await get_tree().create_timer(1.0).timeout
	_refresh_ui()

func _on_aura_connected(connected: bool) -> void:
	status_dot.color = Color.GREEN if connected else Color.RED
	connection_label.text = "AURA: %s" % ("Online" if connected else "Offline")