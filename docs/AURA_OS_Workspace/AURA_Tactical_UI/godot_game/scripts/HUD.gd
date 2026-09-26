## HUD.gd — Interfaz Sci-Fi de AURA para Godot
## Muestra el núcleo 3D, telemetría, logs y estado de agentes/nodos en tiempo real.

extends CanvasLayer

# ─── Nodos principales ───────────────────────────────────────────
@onready var core_mesh: MeshInstance3D = $CoreMesh
@onready var core_light: PointLight3D = $CoreLight
@onready var connection_dot: ColorRect = $ConnectionDot
@onready var status_label: Label = $StatusLabel
@onready var telemetry_container: VBoxContainer = $TelemetryContainer
@onready var agent_list: VBoxContainer = $AgentList
@onready var log_text: RichTextLabel = $LogContainer/LogText

const MAX_LOG_LINES := 6

# ─── Inicialización ─────────────────────────────────────────────
func _ready() -> void:
	AURABridge.connection_changed.connect(_on_connection_changed)
	AURABridge.node_update.connect(_on_node_update)
	AURABridge.task_update.connect(_on_task_update)
	AURABridge.log_event.connect(_on_log_event)

	# Suscripción a canales
	AURABridge.subscribe("node_update")
	AURABridge.subscribe("task_update")

	add_log("[AURA] Inicializando interfaz táctica...")
	_animate_core_idle()

func _process(delta: float) -> void:
	_rotate_core(delta)

# ─── Animaciones del núcleo ─────────────────────────────────────
func _animate_core_idle() -> void:
	if not core_mesh:
		return
	var tween = create_tween()
	tween.set_loops()
	tween.tween_property(core_mesh, "scale", Vector3(1.05, 1.05, 1.05), 1.5)
	tween.tween_property(core_mesh, "scale", Vector3(1.0, 1.0, 1.0), 1.5)

func _rotate_core(delta: float) -> void:
	if core_mesh:
		core_mesh.rotate_y(delta * 0.3)
		core_mesh.rotate_x(delta * 0.1)

func _pulse_light() -> void:
	if core_light:
		var tween = create_tween()
		tween.tween_property(core_light, "light_energy", 2.0, 0.4)
		tween.tween_property(core_light, "light_energy", 1.0, 0.4)

# ─── Eventos del backend ────────────────────────────────────────
func _on_connection_changed(connected: bool) -> void:
	if connection_dot:
		connection_dot.color = Color.GREEN if connected else Color.RED
	if status_label:
		status_label.text = "ONLINE" if connected else "OFFLINE"
	add_log("[SISTEMA] %s" % ("CONECTADO AL BACKEND" if connected else "DESCONECTADO"))

	if connected:
		_pulse_light()

func _on_node_update(nodes: Array) -> void:
	_clear_container(agent_list)
	for node in nodes:
		var item = _create_agent_item(node)
		agent_list.add_child(item)

func _on_task_update(task: Dictionary) -> void:
	var status = task.get("status", "")
	var module = task.get("module", "?")
	var progress = task.get("progress", 0)
	if status == "completed":
		add_log("[TAREA] %s COMPLETADA (%d%%)" % [module, progress])
		_pulse_light()
	elif status == "running":
		add_log("[TAREA] %s EN PROCESO... %d%%" % [module, progress])

func _on_log_event(message: String) -> void:
	add_log(message)

# ─── UI Helpers ──────────────────────────────────────────────────
func add_log(message: String) -> void:
	if not log_text:
		return
	var timestamp = Time.get_datetime_string_from_system().substr(11, 8)
	var line = "[%s] %s" % [timestamp, message]
	if log_text.get_line_count() >= MAX_LOG_LINES:
		log_text.clear()
	log_text.append_text(line + "\n")

func _create_agent_item(node: Dictionary) -> void:
	var hbox = HBoxContainer.new()
	var status_color = Color.GREEN if node.get("status") == "available" else Color.RED
	var indicator = ColorRect.new()
	indicator.color = status_color
	indicator.custom_minimum_size = Vector2(8, 8)
	var label = Label.new()
	label.text = "%s [%s]" % [node.get("name", "?"), node.get("type", "?")]
	label.add_theme_color_override("font_color", Color.CYAN)
	hbox.add_child(indicator)
	hbox.add_child(label)
	agent_list.add_child(hbox)

func _clear_container(container: Container) -> void:
	for child in container.get_children():
		container.remove_child(child)
		child.queue_free()

# ─── Placeholder telemetría (para futura integración) ──────────
func update_telemetry(cpu: float, ram: float, net: float) -> void:
	for label in telemetry_container.get_children():
		if label.name.begins_with("CPU"):
			label.text = "CPU: %.1f%%" % cpu
		elif label.name.begins_with("RAM"):
			label.text = "RAM: %.1f%%" % ram
