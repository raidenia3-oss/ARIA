## RewardBridge.gd — Procesa recompensas cuando un enemigo muere
## Calcula buffs según enemy_type y envía BUFF_GRANTED a AURA

extends Node

## Referencia a AURABridge (autoload global)
var _bridge = null

func _ready() -> void:
	_bridge = get_node("/root/AURABridge")
	print("[RewardBridge] Inicializado")


func process_reward(enemy_data: Dictionary) -> void:
	## Procesa la recompensa de un enemigo derrotado
	## Calcula buff según tipo y aplica en GameState

	var enemy_type = enemy_data.get("type", "MINION")
	var reward_xp = enemy_data.get("reward_xp", 10)

	# Aplicar XP al héroe
	GameState.gain_xp(reward_xp, "kill:" + enemy_data.get("name", "Unknown"))

	# Calcular buff según tipo de enemigo
	var buff = _calculate_buff(enemy_type)

	# Aplicar buff localmente
	if buff.size() > 0:
		GameState.apply_buff(buff.type, buff.value, buff.duration)

		# Notificar a AURA Core
		if _bridge:
			_bridge.send_to_aura("BUFF_GRANTED", {
				"type": buff.type,
				"value": buff.value,
				"duration": buff.duration,
				"enemy_type": enemy_type,
				"enemy_name": enemy_data.get("name", "Unknown"),
				"timestamp": Time.get_unix_time_from_system()
			})

	print("[RewardBridge] Recompensa procesada: ", enemy_type, " → ", buff.type if buff.size() > 0 else "sin buff")


func _calculate_buff(enemy_type: String) -> Dictionary:
	## Calcula el buff a otorgar según el tipo de enemigo
	match enemy_type:
		"BOSS":
			# BOSS: buff de velocidad de escaneo ×2 por 5 minutos
			return {
				"type": "SCAN_SPEED",
				"value": 2.0,
				"duration": 300.0
			}
		"ELITE":
			# ELITE: sube nivel de stealth por 2 minutos
			return {
				"type": "STEALTH_LVL",
				"value": 1.0,
				"duration": 120.0
			}
		"MINION":
			# MINION: boost de XP ×1.1 por 1 minuto
			return {
				"type": "XP_BOOST",
				"value": 1.1,
				"duration": 60.0
			}
		_:
			return {}


func get_active_buffs_summary() -> Array:
	## Retorna las stats de buffs activos para el HUD
	var result = []
	for buff in GameState.active_buffs:
		result.append({
			"type": buff.type,
			"remaining": int(buff.remaining),
			"value": buff.value
		})
	return result