extends Control

var title_label: Label
var earnings_label: Label
var apis_label: Label
var hosting_label: Label
var models_label: Label
var reserve_label: Label
var tier_label: Label
var forecast_label: Label

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
	title_label.text = "[TREASURY]"
	title_label.add_theme_color_override("font_color", Color(0.98, 0.75, 0.14))
	vbox.add_child(title_label)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	earnings_label = Label.new()
	earnings_label.text = "Daily Earnings: $--"
	vbox.add_child(earnings_label)

	apis_label = Label.new()
	apis_label.text = "APIs: $--"
	vbox.add_child(apis_label)

	hosting_label = Label.new()
	hosting_label.text = "Hosting: --"
	vbox.add_child(hosting_label)

	models_label = Label.new()
	models_label.text = "Models: --"
	vbox.add_child(models_label)

	reserve_label = Label.new()
	reserve_label.text = "Reserve: $--"
	vbox.add_child(reserve_label)

	tier_label = Label.new()
	tier_label.text = "Tier: --"
	vbox.add_child(tier_label)

	forecast_label = Label.new()
	forecast_label.text = "7d Forecast: $--"
	vbox.add_child(forecast_label)

func _update():
	if not dashboard:
		return
	var status: Dictionary = dashboard.query_api("/api/brain/treasury/status")
	if status.is_empty():
		return

	earnings_label.text = "Daily Earnings: $%.2f" % float(status.get("daily_earnings", 0))

	var allocation = status.get("allocation", {})
	apis_label.text = "APIs: $%.2f" % float(allocation.get("apis", 0))
	hosting_label.text = "Hosting: %s" % str(allocation.get("hosting", "--"))
	models_label.text = "Models: %s" % str(allocation.get("models", "--"))
	reserve_label.text = "Reserve: $%.2f" % float(allocation.get("reserve", 0))

	tier_label.text = "Tier: %s" % str(status.get("tier", "--")).to_upper()

	var forecast: Dictionary = dashboard.query_api("/api/brain/treasury/forecast?days=7")
	if not forecast.is_empty():
		var total = 0.0
		for day in forecast.get("forecast", []):
			total += float(day.get("projected_earnings", 0))
		forecast_label.text = "7d Forecast: $%.2f" % total
