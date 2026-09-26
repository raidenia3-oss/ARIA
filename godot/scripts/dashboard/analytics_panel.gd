extends Control
class_name AnalyticsPanel

var analytics_data: Dictionary = {}
var update_timer: Timer

func _ready() -> void:
	_build_ui()
	_start_updates()

func _build_ui() -> void:
	var vbox = VBoxContainer.new()
	add_child(vbox)

	var title = Label.new()
	title.text = "[ANALYTICS] Real-Time Insights"
	title.add_theme_font_size_override("font_size", 20)
	vbox.add_child(title)

	var cards = HBoxContainer.new()
	vbox.add_child(cards)
	_create_summary_card(cards, "Events/min", "0", Color.CYAN)
	_create_summary_card(cards, "Quality", "0", Color.GREEN)
	_create_summary_card(cards, "Earnings", "$0", Color.YELLOW)
	_create_summary_card(cards, "Errors", "0%", Color.ORANGE)

	var tabs = TabContainer.new()
	tabs.custom_minimum_size = Vector2(0, 360)
	vbox.add_child(tabs)

	var realtime = VBoxContainer.new()
	_build_realtime_panel(realtime)
	tabs.add_child(realtime)
	tabs.set_tab_title(0, "Real-time")

	var insights = VBoxContainer.new()
	_build_insights_panel(insights)
	tabs.add_child(insights)
	tabs.set_tab_title(1, "Insights")

	var recs = VBoxContainer.new()
	_build_recommendations_panel(recs)
	tabs.add_child(recs)
	tabs.set_tab_title(2, "Recommendations")

	var predictions = VBoxContainer.new()
	_build_predictions_panel(predictions)
	tabs.add_child(predictions)
	tabs.set_tab_title(3, "Predictions")

func _create_summary_card(parent: Container, title: String, value: String, color: Color) -> void:
	var card = PanelContainer.new()
	card.custom_minimum_size = Vector2(130, 70)

	var vbox = VBoxContainer.new()
	card.add_child(vbox)

	var title_label = Label.new()
	title_label.text = title
	title_label.add_theme_color_override("font_color", color)
	vbox.add_child(title_label)

	var value_label = Label.new()
	value_label.text = value
	value_label.add_theme_font_size_override("font_size", 16)
	vbox.add_child(value_label)

	parent.add_child(card)

func _build_realtime_panel(parent: Container) -> void:
	var label = Label.new()
	label.text = "Real-time Metrics (5s refresh)"
	parent.add_child(label)

	var info = Label.new()
	info.text = "Events/min, Response Time, Error Rate, Quality Score"
	parent.add_child(info)

func _build_insights_panel(parent: Container) -> void:
	var label = Label.new()
	label.text = "Automatic Insights"
	parent.add_child(label)

	var list = VBoxContainer.new()
	parent.add_child(list)

func _build_recommendations_panel(parent: Container) -> void:
	var label = Label.new()
	label.text = "Recommendations"
	parent.add_child(label)

	var list = VBoxContainer.new()
	parent.add_child(list)

func _build_predictions_panel(parent: Container) -> void:
	var label = Label.new()
	label.text = "Predictions for Next Hour"
	parent.add_child(label)

	var list = VBoxContainer.new()
	parent.add_child(list)

func _start_updates() -> void:
	update_timer = Timer.new()
	update_timer.wait_time = 5.0
	update_timer.timeout.connect(_update_analytics)
	add_child(update_timer)
	update_timer.start()

func _update_analytics() -> void:
	if AuraClient == null:
		return
	var result = AuraClient.request_json("GET", "/api/analytics/summary")
	if result.is_empty():
		return
	analytics_data = result
	_refresh_display()

func _refresh_display() -> void:
	print("Analytics updated:", analytics_data)

func get_status() -> Dictionary:
	return analytics_data
