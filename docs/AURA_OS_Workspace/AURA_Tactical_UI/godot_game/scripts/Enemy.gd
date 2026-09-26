## Enemy.gd — Comportamiento de un enemigo en el campo de combate idle
## Tiene HP bar, animación de muerte, y emite señal "died" al morir.
## El color del sprite cambia según el tipo: MINION=gris, ELITE=morado, BOSS=rojo.

extends CharacterBody2D

## Señal emitida cuando el enemigo muere, con sus datos para recompensas
signal died(enemy_data: Dictionary)

## === Variables configurables desde el inspector ===
@export var enemy_name: String = "Slime"
@export var enemy_type: String = "MINION"  # MINION / ELITE / BOSS
@export var max_hp: int = 50
@export var reward_xp: int = 10
@export var reward_gold: int = 5

## === Estado interno ===
var hp: int = 50
var is_dead: bool = false

## === Referencias a nodos hijos ===
@onready var sprite: ColorRect = $Sprite2D
@onready var hp_bar: ProgressBar = $HPBar
@onready var name_label: Label = $Label
@onready var anim: AnimationPlayer = $AnimationPlayer


func _ready() -> void:
	## Inicializa el enemigo al aparecer en escena
	hp = max_hp
	hp_bar.max_value = max_hp
	hp_bar.value = max_hp
	name_label.text = enemy_name
	_apply_type_color()
	print("[Enemy] ", enemy_name, " apareció (", enemy_type, ") HP:", max_hp)


func setup(p_name: String, p_type: String, p_hp: int, p_xp: int, p_gold: int) -> void:
	## Configura el enemigo al ser instanciado por EnemySpawner
	enemy_name = p_name
	enemy_type = p_type
	max_hp = p_hp
	hp = p_hp
	reward_xp = p_xp
	reward_gold = p_gold

	hp_bar.max_value = p_hp
	hp_bar.value = p_hp
	name_label.text = enemy_name
	_apply_type_color()


func _apply_type_color() -> void:
	## Asigna color al sprite según el tipo de enemigo
	match enemy_type:
		"MINION":
			sprite.color = Color(0.5, 0.5, 0.5)   # Gris
		"ELITE":
			sprite.color = Color(0.6, 0.2, 0.8)   # Morado
		"BOSS":
			sprite.color = Color(0.8, 0.1, 0.1)   # Rojo
		_:
			sprite.color = Color(0.6, 0.6, 0.6)   # Gris claro


func take_damage(amount: int) -> void:
	## Aplica daño al enemigo, actualiza HP bar, y verifica muerte
	if is_dead:
		return

	hp -= amount
	hp_bar.value = hp

	# Efecto visual de daño: flash rojo temporal
	sprite.color = Color(1, 0.3, 0.3)
	await get_tree().create_timer(0.1).timeout
	_apply_type_color()

	print("[Enemy] ", enemy_name, " recibió ", amount, " daño. HP:", hp, "/", max_hp)

	if hp <= 0:
		die()


func die() -> void:
	## Ejecuta la muerte del enemigo: animación → señal → eliminación
	if is_dead:
		return

	is_dead = true
	print("[Enemy] ", enemy_name, " eliminado.")

	# Preparar datos para RewardBridge
	var enemy_data := {
		"name": enemy_name,
		"type": enemy_type,
		"reward_xp": reward_xp,
		"reward_gold": reward_gold,
		"max_hp": max_hp
	}

	# Animación de muerte (escala + opacidad)
	var tween := create_tween()
	tween.set_parallel(true)
	tween.tween_property(self, "scale", Vector2(1.3, 1.3), 0.15)
	tween.tween_property(self, "modulate:a", 0.0, 0.3)
	tween.tween_property(self, "position:y", position.y - 30, 0.3)

	await tween.finished

	# Emitir señal ANTES de queue_free
	died.emit(enemy_data)

	# Eliminar nodo
	queue_free()