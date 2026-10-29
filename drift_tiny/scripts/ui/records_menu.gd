extends Control
## Local records per track and mode, achievements and career stats.

var _reset_armed := false
var _reset_btn: Button


func _ready() -> void:
	theme = UiTheme.get_theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = UiTheme.BG
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var title := UiTheme.label("RECORDS", 34, UiTheme.PINK)
	title.position = Vector2(30, 18)
	add_child(title)

	var scroll := ScrollContainer.new()
	scroll.position = Vector2(30, 76)
	scroll.size = Vector2(900, 400)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	add_child(scroll)
	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_theme_constant_override("separation", 6)
	scroll.add_child(col)

	var grid := GridContainer.new()
	grid.columns = 6
	grid.add_theme_constant_override("h_separation", 26)
	col.add_child(grid)
	for h in ["TRACK", "MODE", "BEST RACE", "BEST LAP", "BEST DRIFT", "BEST COMBO"]:
		grid.add_child(UiTheme.label(h, 13, UiTheme.DIM))
	var any := false
	var recs: Dictionary = SaveManager.data["records"]
	var keys := recs.keys()
	keys.sort()
	for key in keys:
		var parts := str(key).split("|")
		if parts.size() < 2:
			continue
		var rec: Dictionary = recs[key]
		var mode_key := parts[1]
		var laps_note := ""
		if "_" in mode_key and mode_key.get_slice("_", mode_key.get_slice_count("_") - 1).is_valid_int():
			laps_note = " (%s laps)" % mode_key.get_slice("_", mode_key.get_slice_count("_") - 1)
			mode_key = mode_key.substr(0, mode_key.rfind("_"))
		any = true
		grid.add_child(UiTheme.label(Game.track_def(parts[0]).get("name", parts[0]), 16))
		grid.add_child(UiTheme.label(Game.mode_name(mode_key) + laps_note, 16, UiTheme.CYAN))
		grid.add_child(UiTheme.label(RaceHUD.format_time(float(rec.get("best_time", 0.0))), 16))
		grid.add_child(UiTheme.label(RaceHUD.format_time(float(rec.get("best_lap", 0.0))), 16))
		grid.add_child(UiTheme.label(RaceHUD._fmt_points(int(rec.get("best_score", 0))), 16))
		grid.add_child(UiTheme.label(RaceHUD._fmt_points(int(rec.get("best_combo", 0))), 16))
	if not any:
		col.add_child(UiTheme.label("No records yet — go and set some!", 16, UiTheme.DIM))

	col.add_child(UiTheme.label(" ", 8))
	col.add_child(UiTheme.label("ACHIEVEMENTS", 18, UiTheme.PINK))
	var got: Array = SaveManager.data["achievements"]
	for id in SaveManager.ACHIEVEMENTS.keys():
		var have: bool = id in got
		col.add_child(UiTheme.label(("[x] " if have else "[ ] ") + SaveManager.ACHIEVEMENTS[id], 15,
				UiTheme.TEXT if have else UiTheme.DIM))

	var st: Dictionary = SaveManager.data["stats"]
	col.add_child(UiTheme.label(" ", 8))
	col.add_child(UiTheme.label("CAREER", 18, UiTheme.PINK))
	col.add_child(UiTheme.label("Races: %d    Drift points: %s    Best combo: %s    Distance: %.1f km" % [
		int(st["races"]), RaceHUD._fmt_points(int(st["drift_points"])), RaceHUD._fmt_points(int(st["best_combo"])),
		float(st["distance"]) / 1000.0 * 0.6 / 3.6], 15))

	var buttons := HBoxContainer.new()
	buttons.position = Vector2(30, 486)
	buttons.add_theme_constant_override("separation", 10)
	add_child(buttons)
	var back := UiTheme.button("BACK", Game.goto.bind("menu"), 20)
	back.alignment = HORIZONTAL_ALIGNMENT_CENTER
	back.custom_minimum_size = Vector2(140, 40)
	buttons.add_child(back)
	_reset_btn = UiTheme.button("RESET PROGRESS", _on_reset, 16)
	_reset_btn.alignment = HORIZONTAL_ALIGNMENT_CENTER
	_reset_btn.custom_minimum_size = Vector2(220, 40)
	buttons.add_child(_reset_btn)
	back.grab_focus()


func _on_reset() -> void:
	if not _reset_armed:
		_reset_armed = true
		_reset_btn.text = "PRESS AGAIN TO CONFIRM"
		return
	SaveManager.reset_progress()
	Game.goto("records")


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		Game.goto("menu")
