## AURABridge.gd — Puente entre Godot y AURA Backend
## Expone señales globales para que cualquier escena pueda conectarse al backend WebSocket.

extends Node

signal connection_changed(connected: bool)
signal node_update(nodes: Array)
signal task_update(task: Dictionary)
signal log_event(message: String)
signal send_command(command: String, payload: Dictionary)

var _network: Node = null

func _ready() -> void:
	process_priority = -1
	_network = NetworkController.new()
	add_child(_network)

	_network.connection_changed.connect(connection_changed.emit)
	_network.node_update.connect(node_update.emit)
	_network.task_update.connect(task_update.emit)
	_network.log_event.connect(log_event.emit)

	print("[AURABridge] Autoload listo — NetworkController activo")

func subscribe(channel: String) -> void:
	if _network:
		_network.send_subscribe(channel)

func assign_task(node_id: String, module: String) -> void:
	if _network:
		_network.send_assign_task(node_id, module)

func is_connected() -> bool:
	return _network.is_connected() if _network else false
