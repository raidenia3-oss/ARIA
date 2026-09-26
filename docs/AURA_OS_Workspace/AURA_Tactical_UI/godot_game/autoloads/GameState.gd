## GameState.gd — Persistencia del juego usando ConfigFile
## Guarda stats del héroe, xp, level, gold, buffs activos e historial.
## Sincroniza con AURA Core cada 30s via AURABridge.

extends Node

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PERSISTENCIA
# ═══════════════════════════════════════════════════════════════

const SAVE_PATH := "user://game_state.cfg"
const SYNC_INTERVAL := 30.0  # Segundos entre sincronizaciones con AURA

# ═══════════════════════════════════════════════════════════════
# SEÑALES
# ═══════════════════════════════════════════════════════════════

signal level_changed(new_level: int)
signal xp_changed(new_xp: int)
signal gold_changed(new_gold: int)
signal buff_applied(buff: Dictionary)
signal stats_changed(stats: Dictionary)

# ═══════════════════════════════════════════════════════════════
# ESTADO DEL HÉROE
# ═══════════════════════════════════════════════════════════════

var level: int = 1
var xp: int = 0
var xp_to_next: int = 100
var gold: int = 0

## Stats del héroe
var stats := {
	"attack": 10,
	"defense": 8,
	"stamina": 100,
	"max_stamina": 100,
	"speed": 5,
	"crit_chance": 0.05,
	"xp_bonus": 0.0,  # Bonus de XP del ecosistema AURA
	"stamina_regen": 1.0  # Regeneración por tick
}

## Buffs activos
var active_buffs: Array[Dictionary] = []

## Historial de misiones completadas
var mission_history: Array[Dictionary] = []

## Timestamps
var last_save: float = 0.0
var last_sync_aura: float = 0.0
var play_time: float = 0.0


# ═══════════════════════════════════════════════════════════════
# CICLO DE VIDA
# ═══════════════════════════════════════════════════════════════

func _ready() -> void:
	print("[GameState] Cargando estado del juego...")
	load_state()
	# Conectar a AURABridge para recibir telemetría
	if AURABridge:
		AURABridge.aura_telemetry.connect(_on_aura_telemetry)
		AURABridge.aura_connection_changed.connect(_on_aura_connection)
		AURABridge.aura_buff_granted.connect(_on_aura_buff)


func _process(delta: float) -> void:
	play_time += delta
	# Regenerar stamina
	if stats.stamina < stats.max_stamina:
		stats.stamina = min(stats.max_stamina, stats.stamina + stats.stamina_regen * delta)
		stats_changed.emit(stats)
	# Guardar cada 30s
	if play_time - last_save >= 30.0:
		save_state()
		last_save = play_time
	# Sincronizar con AURA cada 30s
	if play_time - last_sync_aura >= SYNC_INTERVAL:
		sync_with_aura()
		last_sync_aura = play_time


func _notification(what: int) -> void:
	# Guardar al salir
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_WM_GO_BACK_REQUEST:
		save_state()
		print("[GameState] Estado guardado al salir")


# ═══════════════════════════════════════════════════════════════
# MÉTODOS PÚBLICOS
# ═══════════════════════════════════════════════════════════════

## Añade XP al héroe. Retorna true si subió de nivel.
func gain_xp(amount: int, source: String = "") -> bool:
	var bonus = amount * stats.xp_bonus
	xp += int(amount + bonus)
	xp_changed.emit(xp)
	if xp >= xp_to_next:
		level_up()
		return true
	return false


## Sube un nivel al héroe.
func level_up() -> void:
	while xp >= xp_to_next:
		xp -= xp_to_next
		level += 1
		xp_to_next = _calc_xp_for_level(level)
		# Bonus por nivel
		stats.attack += 2
		stats.defense += 1
		stats.max_stamina += 10
		stats.speed += 1
		stats.stamina_regen += 0.2
	level_changed.emit(level)
	stats_changed.emit(stats)
	# Notificar a AURA
	if AURABridge:
		AURABridge.report_level_up(level, stats)
	print("[GameState] ¡Nivel! Ahora eres nivel ", level)
	save_state()


## Añade oro al héroe.
func gain_gold(amount: int, source: String = "") -> void:
	gold += amount
	gold_changed.emit(gold)
	print("[GameState] +", amount, " gold (", source, ")")


## Aplica un buff al héroe.
func apply_buff(type: String, value: float, duration: float) -> void:
	var buff := {
		"type": type,
		"value": value,
		"remaining": duration,
		"applied_at": play_time
	}
	active_buffs.append(buff)
	# Aplicar efecto
	match type:
		"attack_up":
			stats.attack += int(value)
		"defense_up":
			stats.defense += int(value)
		"speed_up":
			stats.speed += int(value)
		"stamina_regen":
			stats.stamina_regen += value
		"xp_boost":
			stats.xp_bonus += value
	buff_applied.emit(buff)
	stats_changed.emit(stats)
	print("[GameState] Buff aplicado: ", type, " +", value, " por ", duration, "s")


## Quita un buff al héroe (cuando expira).
func remove_buff(index: int) -> void:
	if index < 0 or index >= active_buffs.size():
		return
	var buff = active_buffs[index]
	# Revertir efecto
	match buff.type:
		"attack_up":
			stats.attack -= int(buff.value)
		"defense_up":
			stats.defense -= int(buff.value)
		"speed_up":
			stats.speed -= int(buff.value)
		"stamina_regen":
			stats.stamina_regen -= buff.value
		"xp_boost":
			stats.xp_bonus -= buff.value
	active_buffs.remove_at(index)
	stats_changed.emit(stats)


## Actualiza buffs (reduce tiempo restante, remueve expirados).
func update_buffs(delta: float) -> void:
	var to_remove: Array[int] = []
	for i in range(active_buffs.size() - 1, -1, -1):
		active_buffs[i].remaining -= delta
		if active_buffs[i].remaining <= 0:
			to_remove.append(i)
	for i in to_remove:
		remove_buff(i)


## Registra una misión completada.
func log_mission(mission_name: String, success: bool, xp_earned: int, gold_earned: int) -> void:
	mission_history.append({
		"name": mission_name,
		"success": success,
		"xp": xp_earned,
		"gold": gold_earned,
		"timestamp": Time.get_datetime_string_from_system()
	})
	# Mantener solo las últimas 50 misiones
	if mission_history.size() > 50:
		mission_history = mission_history.slice(-50)
	gain_xp(xp_earned, "mission:" + mission_name)
	gain_gold(gold_earned, "mission:" + mission_name)


# ═══════════════════════════════════════════════════════════════
# PERSISTENCIA
# ═══════════════════════════════════════════════════════════════

func save_state() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("hero", "level", level)
	cfg.set_value("hero", "xp", xp)
	cfg.set_value("hero", "xp_to_next", xp_to_next)
	cfg.set_value("hero", "gold", gold)
	cfg.set_value("hero", "play_time", play_time)
	cfg.set_value("stats", "", stats)
	cfg.set_value("buffs", "active", active_buffs)
	cfg.set_value("history", "missions", mission_history)
	cfg.save(SAVE_PATH)
	last_save = play_time


func load_state() -> void:
	var cfg := ConfigFile.new()
	var err = cfg.load(SAVE_PATH)
	if err == OK:
		level = cfg.get_value("hero", "level", 1)
		xp = cfg.get_value("hero", "xp", 0)
		xp_to_next = cfg.get_value("hero", "xp_to_next", 100)
		gold = cfg.get_value("hero", "gold", 0)
		play_time = cfg.get_value("hero", "play_time", 0.0)
		var loaded_stats = cfg.get_value("stats", "", null)
		if loaded_stats != null:
			stats = loaded_stats
		active_buffs = cfg.get_value("buffs", "active", [])
		mission_history = cfg.get_value("history", "missions", [])
		print("[GameState] Estado cargado: Nivel ", level, ", XP ", xp, "/", xp_to_next)
	else:
		print("[GameState] Sin estado previo, creando estado inicial")


func reset_state() -> void:
	level = 1
	xp = 0
	xp_to_next = 100
	gold = 0
	stats = {
		"attack": 10, "defense": 8, "stamina": 100, "max_stamina": 100,
		"speed": 5, "crit_chance": 0.05, "xp_bonus": 0.0, "stamina_regen": 1.0
	}
	active_buffs.clear()
	mission_history.clear()
	save_state()
	print("[GameState] Estado reseteado")


# ═══════════════════════════════════════════════════════════════
# SINCRONIZACIÓN CON AURA
# ═══════════════════════════════════════════════════════════════

func sync_with_aura() -> void:
	if AURABridge and AURABridge.is_connected_to_aura():
		AURABridge.sync_hero_data({
			"level": level,
			"xp": xp,
			"gold": gold,
			"stats": stats,
			"play_time": play_time
		})
		last_sync_aura = play_time


func _on_aura_telemetry(data: Dictionary) -> void:
	# Aplicar bonus de telemetría de AURA si existen
	var hero_stats = data.get("hero_stats", {})
	if hero_stats.has("stamina_bonus"):
		stats.stamina_regen += hero_stats["stamina_bonus"]
		stats_changed.emit(stats)


func _on_aura_connection(connected: bool) -> void:
	if connected:
		print("[GameState] AURA conectado, sincronizando estado...")
		sync_with_aura()


func _on_aura_buff(buff_data: Dictionary) -> void:
	apply_buff(buff_data.get("type", ""), buff_data.get("value", 0.0), buff_data.get("duration", 10.0))


# ═══════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════

func _calc_xp_for_level(lvl: int) -> int:
	return 100 + (lvl * 50)


func get_save_data() -> Dictionary:
	return {
		"level": level, "xp": xp, "xp_to_next": xp_to_next,
		"gold": gold, "stats": stats, "play_time": play_time,
		"buffs": active_buffs.size(), "missions": mission_history.size()
	}