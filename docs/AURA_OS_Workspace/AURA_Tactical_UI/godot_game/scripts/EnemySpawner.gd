## EnemySpawner.gd — Genera enemigos según eventos de AURA
## Se conecta a AURABridge.aura_enemy_spawn para recibir enemigos desde VULN_SCANNER
## Máximo 10 enemigos simultáneos en pantalla

extends Node2D

## Escena del enemigo a instanciar
const EnemyScene = preload("res://scenes/Enemy.tscn")

## Número máximo de enemigos simultáneos
const MAX_ENEMIES := 10

## Referencia al nodo padre de enemigos (se establece en GameWorld)
@export var enemies_container: NodePath

## Señal emitida cuando un enemigo muere
signal enemy_killed(enemy_data: Dictionary)

## Almacén de enemigos activos
var _active_enemies: Array[Node] = []

func _ready() -> void:
	## Conectar señales de AURA y del sistema de combate
	AURABridge.aura_enemy_spawn.connect(_on_aura_enemy_spawn)

	# Conectar señales de IdleRPGCore si existe
	var idle_core = get_node_or_null("/root/GameWorld/IdleRPGCore")
	if idle_core:
		idle_core.combat_tick.connect(_on_combat_tick)

	print("[EnemySpawner] Inicializado. Máximo enemigos:", MAX_ENEMIES)


func _on_aura_enemy_spawn(enemies: Array) -> void:
	## Callback cuando AURA envía datos de enemigos para spawnear
	for enemy_data in enemies:
		if _active_enemies.size() >= MAX_ENEMIES:
			print("[EnemySpawner] Límite de enemigos alcanzado (", MAX_ENEMIES, ")")
			break

		_spawn_enemy(enemy_data)


func spawn_from_vuln_scanner(vuln_data: Dictionary) -> void:
	## Genera enemigos a partir de datos de vulnerabilidades reales
	var risk = vuln_data.get("risk", "LOW")
	var hp = 0
	var xp = 0
	var enemy_type = "MINION"

	match risk:
		"HIGH":
			hp = 200
			xp = 50
			enemy_type = "BOSS"
		"MEDIUM":
			hp = 80
			xp = 25
			enemy_type = "ELITE"
		_:
			hp = 30
			xp = 10
			enemy_type = "MINION"

	var enemy_data := {
		"name": vuln_data.get("name", "Unknown"),
		"type": enemy_type,
		"hp": hp,
		"reward_xp": xp,
		"reward_gold": xp / 3
	}

	_spawn_enemy(enemy_data)


func _spawn_enemy(data: Dictionary) -> void:
	## Instancia un enemigo y lo coloca en el contenedor
	var enemy = EnemyScene.instantiate()
	enemy.setup(
		data.get("name", "Unknown"),
		data.get("type", "MINION"),
		data.get("hp", 30),
		data.get("reward_xp", 10),
		data.get("reward_gold", 5)
	)

	# Posición aleatoria dentro de los límites de pantalla
	var viewport_size = get_viewport_rect().size
	enemy.position = Vector2(
		randf_range(100, viewport_size.x - 100),
		randf_range(200, viewport_size.y - 100)
	)

	# Conectar señal de muerte
	enemy.died.connect(_on_enemy_died)

	# Añadir al contenedor o como hijo directo
	var container = get_node_or_null(enemies_container) if enemies_container else null
	if container:
		container.add_child(enemy)
	else:
		add_child(enemy)

	_active_enemies.append(enemy)
	print("[EnemySpawner] Enemigo spawneado: ", enemy.enemy_name, " en ", enemy.position)


func _on_combat_tick(damage: int, _enemy_name: String) -> void:
	## Aplica el daño del tick de combate a todos los enemigos activos
	for enemy in _active_enemies:
		if is_instance_valid(enemy) and not enemy.is_dead:
			enemy.take_damage(damage)
			break  # Solo ataca al primer enemigo vivo (idle)


func _on_enemy_died(enemy_data: Dictionary) -> void:
	## Callback cuando un enemigo muere: notifica y limpia
	_active_enemies = _active_enemies.filter(func(e): return is_instance_valid(e))

	# Notificar al mundo de juego
	enemy_killed.emit(enemy_data)

	# Enviar buff a AURA
	if RewardBridge:
		RewardBridge.process_reward(enemy_data)

	print("[EnemySpawner] Enemigo eliminado. Quedan: ", _active_enemies.size())


func get_enemy_count() -> int:
	return _active_enemies.size()