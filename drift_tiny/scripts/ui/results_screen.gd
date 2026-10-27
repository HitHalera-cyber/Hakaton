class_name ResultsScreen
extends Control
## End-of-race overlay: winner, times, drift points, best combo, rewards,
## new records and unlocked achievements.

var _content: VBoxContainer


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	theme = UiTheme.get_theme()
	visible = false


## data: {title, subtitle, columns: [..], rows: [[cells], ...], row_colors: [Color],
##        notes: [String], buttons: [[label, Callable], ...]}
func show_results(data: Dictionary) -> void:
	for c in get_children():
		c.queue_free()
	add_child(UiTheme.dimmer(0.7))
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := UiTheme.panel()
	panel.custom_minimum_size = Vector2(700, 0)
	center.add_child(panel)
	_content = VBoxContainer.new()
	_content.add_theme_constant_override("separation", 8)
	panel.add_child(_content)
	_content.add_child(UiTheme.label(data.get("title", "RESULTS"), 34, UiTheme.PINK))
	if data.has("subtitle"):
		_content.add_child(UiTheme.label(data["subtitle"], 16, UiTheme.DIM))

	var cols: Array = data.get("columns", [])
	var grid := GridContainer.new()
	grid.columns = cols.size()
	grid.add_theme_constant_override("h_separation", 22)
	grid.add_theme_constant_override("v_separation", 4)
	_content.add_child(grid)
	for c in cols:
		grid.add_child(UiTheme.label(str(c), 13, UiTheme.DIM))
	var rows: Array = data.get("rows", [])
	var colors: Array = data.get("row_colors", [])
	for r in rows.size():
		var row: Array = rows[r]
		var col: Color = colors[r] if r < colors.size() else UiTheme.TEXT
		for k in row.size():
			grid.add_child(UiTheme.label(str(row[k]), 18 if k < 2 else 16, col if k < 2 else UiTheme.TEXT))

	for n in data.get("notes", []):
		_content.add_child(UiTheme.label(str(n), 15, UiTheme.CYAN))

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 12)
	_content.add_child(buttons)
	var first: Button = null
	for b in data.get("buttons", []):
		var btn := UiTheme.button(str(b[0]), b[1], 20)
		btn.alignment = HORIZONTAL_ALIGNMENT_CENTER
		buttons.add_child(btn)
		if first == null:
			first = btn
	visible = true
	if first:
		first.call_deferred("grab_focus")
	AudioManager.play("reward")
