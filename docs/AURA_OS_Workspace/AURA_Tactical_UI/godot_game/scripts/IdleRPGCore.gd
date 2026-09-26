## IdleRPGCore.gd — Lógica de combate idle automático
## Ejecuta combate cada 2 segundos, usa hero_stats de GameState,
## emite señales de XP, nivel y buffs.

extends Node

# Señales que emite cuando ocurren eventos de combate
signal xp_gained(amount: int, source: String)
signal leveled_up(new_level: int)
signal combat_tick(damage: int, enemy_name: String)

# Intervalo de combate automático en segundos
const COMBAT_INTERVAL := 2.0

var _timer: float = 0.0

func _ready() -> void:
	# Conectar señales de GameState para nivel
	GameState.level_changed.connect(_on_level_changed)
	print("[IdleRPGCore] Motor de combate idle iniciado")


func _process(delta: float) -> void:
	_timer += delta
	if _timer >= COMBAT_INTERVAL:
		_timer -= COMBAT_INTERVAL
		_perform_combat_tick()


func _perform_combat_tick() -> void:
	## Ejecuta un tick de combate automático
	## El daño base se calcula desde hero_stats
	var stats = GameState.stats
	var base_damage = stats.attack + (stats.speed * 0.5)

	# Chance de golpe crítico
	var is_crit = randf() < stats.crit_chance
	var damage = int(base_damage * (2.0 if is_crit else 1.0))

	combat_tick.emit(damage, "idle")

	# Recompensa mínima por cada tick de combate
	var xp_reward = max(1, damage / 5)
	GameState.gain_xp(xp_reward, "combat_idle")
	xp_gained.emit(xp_reward, "combat_idle")


func force_combat_tick() -> void:
	## Permite ejecutar un tick de combate manualmente
	_perform_combat_tick()


func get_hero_damage() -> int:
	## Retorna el daño base actual del héroe
	var stats = GameState.stats
	return stats.attack + (int)(stats.speed * 0.5)


func _on_level_changed(new_level: int) -> void:
	## Callback cuando el héroe sube de nivel
	print("[IdleRPGCore] ¡Subió a nivel ", new_level, "! Daño base: ", get_hero_damage())
	leveled_up.emit(new_level)


func get_stats_summary() -> String:
	## Retorna un resumen legible de las stats del héroe
	var s = GameState.stats
	return "ATK:{0} DEF:{1} HP:{2}/{3} SPD:{4} CRIT:{5}%".format([
		s.attack, s.defense, s.stamina, s.max_stamina, s.speed, int(s.crit_chance * 100)
	])