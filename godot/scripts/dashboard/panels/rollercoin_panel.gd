extends Control

var title_label: Label
var status_label: Label
var progress_bar: ProgressBar
var earnings_label: Label
var last_claim_label: Label

var dashboard: DashboardManager

func _ready():
	dashboard = _find_dashboard()
	_build_ui()

func _find_dashboard() -> DashboardManager:
	var node = get_parent()
	while node:
		if node is DashboardManager:
			return node
		node = node.get_parent()
	return null

func _build_ui():
	var vbox = VBoxContainer.new()
	vbox.anchor_right = 1.0
	vbox.anchor_bottom = 1.0
	vbox.offset_left = 10
	vbox.offset_top = 10
	vbox.offset_right = -10
	vbox.offset_bottom = -10
	add_child(vbox)

	title_label = Label.new()
	title_label.text = "[ROLLERCOIN] BOT"
	title_label.add_theme_color_override("font_color", Color(0.86, 0.15, 0.15))
	vbox.add_child(title_label)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	status_label = Label.new()
	status_label.text = "Status: checking..."
	vbox.add_child(status_label)

	var goal_label = Label.new()
	goal_label.text = "Daily Goal: $150"
	vbox.add_child(goal_label)

	progress_bar = ProgressBar.new()
	progress_bar.value = 0
	progress_bar.custom_minimum_size = Vector2(0, 18)
	vbox.add_child(progress_bar)

	earnings_label = Label.new()
	earnings_label.text = "Today: $--"
	vbox.add_child(earnings_label)

	last_claim_label = Label.new()
	last_claim_label.text = "Last Claim: --"
	vbox.add_child(last_claim_label)

func _update():
	if not dashboard:
		return
	var status: Dictionary = dashboard.query_api("/api/rollercoin/status")
	if status.is_empty():
		return

	var running = bool(status.get("running", false))
	status_label.text = "Status: %s" % ("RUNNING" if running else "STOPPED")

	var daily = float(status.get("daily_earnings", 0))
	var goal = float(status.get("goal", 150))
	var progress = (daily / goal) * 100.0 if goal > 0 else 0.0

	progress_bar.value = min(progress, 100)
	earnings_label.text = "Today: $%.2f" % daily

	if progress >= 100:
		progress_bar.modulate = Color(0.2, 0.8, 0.2)
	elif progress >= 70:
		progress_bar.modulate = Color(0.98, 0.75, 0.14)
	else:
		progress_bar.modulate = Color(0.86, 0.15, 0.15)

	last_claim_label.text = "Last Claim: %s" % str(status.get("last_claim", "--"))
