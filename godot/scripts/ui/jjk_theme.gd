class_name JJKTheme
extends Node

const BG := Color("#05070a")
const PANEL := Color("#0f1219")
const ACCENT := Color("#7c4dff")
const ACCENT2 := Color("#00e5ff")
const TEXT := Color("#e6e9f0")
const TEXT_DIM := Color("#6b7280")
const RED := Color("#ff4d4d")
const GREEN := Color("#00e676")
const YELLOW := Color("#ffea00")
const CYAN := Color("#00e5ff")
const PURPLE := Color("#7c4dff")
const VOID_BLACK := Color("#0a0a0f")
const CURSED_ENERGY := Color("#8a2be2")


static func apply_panel(panel: Panel) -> void:
	if not panel:
		return
	var style := StyleBoxFlat.new()
	style.bg_color = PANEL
	style.border_color = ACCENT2
	style.border_width_left = 1
	style.border_width_right = 1
	style.border_width_top = 1
	style.border_width_bottom = 1
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	panel.add_theme_stylebox_override("panel", style)


static func apply_button(button: Button) -> void:
	if not button:
		return
	var style := StyleBoxFlat.new()
	style.bg_color = ACCENT
	style.border_color = ACCENT2
	style.border_width_left = 1
	style.border_width_right = 1
	style.border_width_top = 1
	style.border_width_bottom = 1
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	button.add_theme_stylebox_override("normal", style)
	button.add_theme_color_override("font_color", TEXT)


static func glow_color(base: Color, intensity: float = 0.6) -> Color:
	return Color(
		min(1.0, base.r + (1.0 - base.r) * intensity),
		min(1.0, base.g + (1.0 - base.g) * intensity),
		min(1.0, base.b + (1.0 - base.b) * intensity),
		base.a
	)


static func cursed_energy_gradient(step: int, total: int) -> Color:
	var ratio := 0.0 if total <= 1 else float(step) / float(total - 1)
	return Color(
		138.0 / 255.0 + (0.0 - 138.0 / 255.0) * ratio,
		43.0 / 255.0 + (229.0 / 255.0 - 43.0 / 255.0) * ratio,
		226.0 / 255.0 + (255.0 / 255.0 - 226.0 / 255.0) * ratio,
		1.0
	)


static func show_toast(text: String) -> void:
	# Muestra un toast simple en la UI (si hay árbol de escena).
	var tree := Engine.get_main_loop()
	if not tree or not (tree as SceneTree).root:
		print("TOAST: %s" % text)
		return
	var root := (tree as SceneTree).root
	var canvas := CanvasLayer.new()
	root.add_child(canvas)
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", ACCENT2)
	label.position = Vector2(20, root.size.y - 40)
	canvas.add_child(label)
	var tween := label.create_tween()
	tween.tween_property(label, "modulate:a", 0.0, 2.0).set_delay(1.0)
	tween.tween_callback(func():
		label.queue_free()
		canvas.queue_free()
	)
