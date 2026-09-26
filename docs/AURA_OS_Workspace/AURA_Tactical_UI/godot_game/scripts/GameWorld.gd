## GameWorld.gd — Escena principal del mundo idle
## Conecta todas las señales entre nodos hijos: IdleRPGCore, EnemySpawner, RewardBridge, HUD
## Pausa si AURABridge pierde conexión más de 30 segundos

extends Node2D

var _disconnected_time: float = 0.0
var _pause_threshold: float = 30.0

func _ready() -> void:
	# Conectar señal de muerte de EnemySpawner → RewardBridge
	var spawner = $EnemySpawner
	if spawner:
		spawner.enemy_killed.connect($RewardBridge.process_reward)

	# Conectar nivel subido → HUD
	var idle = $IdleRPGCore
	if idle:
		idle.leveled_up.connect($HUD._on_level_changed)

	# Conectar eventos AURA → EnemySpawner
	if AURABridge:
		AURABridge.aura_enemy_spawn.connect($EnemySpawner._on_aura_enemy_spawn)

	# Pausa automática si AURA se desconecta
	if AURABridge:
		AURABridge.aura_connection_changed.connect(_on_aura_connection)

	print("[GameWorld] Mundo idle inicializado. Conectado a AURA.")

func _process(delta: float) -> void:
	# Verificar tiempo de desconexión
	if not AURABridge.is_connected_to_aura():
		_disconnected_time += delta
		if _disconnected_time >= _pause_threshold and not get_tree().paused:
			get_tree().paused = true
			_show_pause_overlay()
			print("[GameWorld] Juego pausado por desconexión AURA >30s")
	else:
		if _disconnected_time > 0 and get_tree().paused:
			get_tree().paused = false
			_hide_pause_overlay()
		_disconnected_time = 0.0

func _on_aura_connection(connected: bool) -> void:
	if connected:
		_disconnected_time = 0.0
		if get_tree().paused:
			get_tree().paused = false
			_hide_pause_overlay()
			print("[GameWorld] Reconectado a AURA. Juego reanudado.")

func _show_pause_overlay() -> void:
	var overlay = $PauseOverlay
	if overlay:
		overlay.visible = true

func _hide_pause_overlay() -> void:
	var overlay = $PauseOverlay
	if overlay:
		overlay.visible = false