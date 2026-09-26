extends Control

var title_label: Label
var status_label: Label
var teacher_acc: Label
var student_acc: Label
var gap_label: Label
var last_label: Label

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
	title_label.text = "[TRAINING] FEDERATED"
	title_label.add_theme_color_override("font_color", Color(0.66, 0.33, 0.97))
	vbox.add_child(title_label)

	var sep = HSeparator.new()
	vbox.add_child(sep)

	status_label = Label.new()
	status_label.text = "Status: IDLE"
	vbox.add_child(status_label)

	teacher_acc = Label.new()
	teacher_acc.text = "Teacher: --"
	vbox.add_child(teacher_acc)

	student_acc = Label.new()
	student_acc.text = "Student: --"
	vbox.add_child(student_acc)

	gap_label = Label.new()
	gap_label.text = "Gap: --"
	vbox.add_child(gap_label)

	last_label = Label.new()
	last_label.text = "Last: --"
	vbox.add_child(last_label)

func _update():
	if not dashboard:
		return
	var status: Dictionary = dashboard.query_api("/api/brain/training/status")
	if status.is_empty():
		return

	status_label.text = "Status: %s" % str(status.get("status", "unknown")).to_upper()

	var distill = status.get("distillation_stats", {})
	if distill.is_empty():
		distill = status

	var teacher_conf = float(distill.get("average_teacher_confidence", 0.92))
	var student_conf = float(distill.get("average_student_confidence", 0.78))
	var gap = float(distill.get("gap_to_close", teacher_conf - student_conf))

	teacher_acc.text = "Teacher: %.0f%%" % (teacher_conf * 100)
	student_acc.text = "Student: %.0f%%" % (student_conf * 100)
	gap_label.text = "Gap: %.1f%%" % (gap * 100)

	if gap < 0.10:
		gap_label.add_theme_color_override("font_color", Color(0.2, 0.8, 0.2))
	else:
		gap_label.add_theme_color_override("font_color", Color(0.98, 0.75, 0.14))

	last_label.text = "Last: %s" % str(status.get("last_checkpoint", "--"))
