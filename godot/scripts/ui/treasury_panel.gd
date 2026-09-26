extends Control
class_name TreasuryPanel

@onready var status_label: Label = $Margin/VBox/StatusLabel
@onready var earnings_today_label: Label = $Margin/VBox/EarningsTodayLabel
@onready var api_budget_label: Label = $Margin/VBox/ApiBudgetLabel
@onready var hosting_tier_label: Label = $Margin/VBox/HostingTierLabel
@onready var model_label: Label = $Margin/VBox/ModelLabel
@onready var reserve_label: Label = $Margin/VBox/ReserveLabel
@onready var projection_label: Label = $Margin/VBox/ProjectionLabel

var _client: AuraClient
var _update_timer: Timer


func _ready() -> void:
	_client = get_tree().root.get_node_or_null("AuraClient")
	if not _client:
		push_error("[TreasuryPanel] AuraClient not found")
		return
	_update_timer = Timer.new()
	_update_timer.wait_time = 10.0
	_update_timer.timeout.connect(_fetch_status)
	add_child(_update_timer)
	_update_timer.start()
	_fetch_status()


func _fetch_status() -> void:
	if not _client:
		return
	var treasury := _client.request_json("/api/brain/treasury/status")
	if treasury.is_empty():
		status_label.text = "Treasury: offline"
		return
	status_label.text = "Treasury: online"
	_render_treasury(treasury)


func _render_treasury(treasury: Dictionary) -> void:
	var api_budget = treasury.get("api_budget", {})
	var hosting = treasury.get("hosting", {})
	var models = treasury.get("models", {})
	var reserve = treasury.get("reserve", {})

	var api_remaining = float(api_budget.get("remaining", 0.0))
	var hosting_remaining = float(hosting.get("budget_remaining", 0.0))
	var models_remaining = float(models.get("budget_remaining", 0.0))
	var reserve_balance = float(reserve.get("reserve_balance", 0.0))

	earnings_today_label.text = "Today: $%.2f" % max(api_remaining + hosting_remaining + models_remaining + reserve_balance, 0.0)
	api_budget_label.text = "APIs: $%.2f (used %.1f%%)" % [float(api_budget.get("daily_budget", 0.0)), float(api_budget.get("percentage_used", 0.0))]
	hosting_tier_label.text = "Hosting: %s (%s GB RAM)" % [str(hosting.get("current_tier", "free")), str(hosting.get("ram_gb", 0.0))]
	model_label.text = "Model: %s" % str(models.get("current_model", "Qwen-0.5B"))
	reserve_label.text = "Reserve: $%.2f" % reserve_balance
	projection_label.text = "7d Forecast: loaded"
