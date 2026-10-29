extends Control
## Race setup: players, mode, track, laps, split/shared view and car choice.

var _players: Widgets.OptionCycler
var _mode: Widgets.OptionCycler
var _track: Widgets.OptionCycler
var _laps: Widgets.OptionCycler
var _view: Widgets.OptionCycler
var _car1: Widgets.OptionCycler
var _car2: Widgets.OptionCycler
var _desc: Label
var _record: Label
var _preview: Widgets.TrackPreview
var _track_name: Label
var _car_preview: Widgets.CarPreview
var _start: Button


func _ready() -> void:
	theme = UiTheme.get_theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = UiTheme.BG
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var title := UiTheme.label("RACE SETUP", 34, UiTheme.PINK)
	title.position = Vector2(40, 24)
	add_child(title)

	var col := VBoxContainer.new()
	col.position = Vector2(40, 84)
	col.add_theme_constant_override("separation", 4)
	add_child(col)

	_players = Widgets.OptionCycler.new("PLAYERS", ["1 Player", "2 Players"], [1, 2], Game.players - 1)
	_players.changed.connect(func(_v): _on_players_changed())
	col.add_child(_players)
	_mode = Widgets.OptionCycler.new("MODE", [], [])
	_mode.changed.connect(func(_v): _refresh_info())
	col.add_child(_mode)
	var tnames: Array = []
	for t in Game.tracks:
		tnames.append(t["name"])
	_track = Widgets.OptionCycler.new("TRACK", tnames, Game.track_ids(), Game.track_ids().find(Game.track_id))
	_track.changed.connect(func(_v): _refresh_info())
	col.add_child(_track)
	_laps = Widgets.OptionCycler.new("LAPS", ["1", "2", "3", "4", "5"], [1, 2, 3, 4, 5], Game.laps - 1)
	col.add_child(_laps)
	_view = Widgets.OptionCycler.new("2P SCREEN", ["Split screen", "Shared camera"], ["split", "shared"],
			0 if Game.view_mode == "split" else 1)
	col.add_child(_view)
	_car1 = Widgets.OptionCycler.new("1P CAR", [], [])
	_car1.changed.connect(func(_v): _refresh_info())
	col.add_child(_car1)
	_car2 = Widgets.OptionCycler.new("2P CAR", [], [])
	col.add_child(_car2)
	_fill_cars()

	_desc = UiTheme.label("", 15, UiTheme.DIM)
	_desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_desc.custom_minimum_size = Vector2(420, 44)
	col.add_child(_desc)

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 10)
	col.add_child(buttons)
	_start = UiTheme.button("START RACE", _on_start, 24)
	_start.alignment = HORIZONTAL_ALIGNMENT_CENTER
	_start.custom_minimum_size = Vector2(220, 44)
	buttons.add_child(_start)
	var back := UiTheme.button("BACK", Game.goto.bind("menu"), 20)
	back.alignment = HORIZONTAL_ALIGNMENT_CENTER
	back.custom_minimum_size = Vector2(120, 44)
	buttons.add_child(back)

	# Right side: track preview, record, car.
	_track_name = UiTheme.label("", 20, UiTheme.TEXT)
	_track_name.position = Vector2(520, 84)
	_track_name.size = Vector2(400, 30)
	_track_name.clip_text = true
	add_child(_track_name)
	_preview = Widgets.TrackPreview.new()
	_preview.position = Vector2(520, 120)
	_preview.size = Vector2(400, 230)
	add_child(_preview)
	_record = UiTheme.label("", 15, UiTheme.CYAN)
	_record.position = Vector2(520, 358)
	add_child(_record)
	_car_preview = Widgets.CarPreview.new()
	_car_preview.position = Vector2(760, 380)
	_car_preview.size = Vector2(150, 140)
	_car_preview.zoom = 5.0
	add_child(_car_preview)

	_on_players_changed()
	if Game.has_meta("focus_track"):
		Game.remove_meta("focus_track")
		_track.grab_focus()
	else:
		_start.grab_focus()
	AudioManager.play_music("menu")


func _fill_cars() -> void:
	var names: Array = []
	var ids: Array = []
	for c in Game.cars:
		if SaveManager.is_unlocked(c["id"]):
			names.append(c["name"])
			ids.append(c["id"])
	_car1.set_options(names, ids, SaveManager.get_selected(1))
	_car2.set_options(names, ids, SaveManager.get_selected(2))


func _on_players_changed() -> void:
	var p: int = _players.value()
	var keys := Game.modes_for(p)
	var labels: Array = []
	for k in keys:
		labels.append(Game.mode_name(k))
	var keep: String = Game.mode if Game.mode in keys else str(keys[0])
	_mode.set_options(labels, keys, keep)
	_view.visible = p == 2
	_car2.visible = p == 2
	_refresh_info()


func _refresh_info() -> void:
	var m: String = _mode.value()
	_desc.text = Game.MODES[m]["desc"]
	_laps.visible = m != "practice" and m != "championship"
	var tid: String = _track.value()
	if m == "championship":
		tid = Game.track_ids()[0]
		_track.disabled = true
	else:
		_track.disabled = false
	var td := Game.track_data(tid)
	_preview.set_track(td)
	_track_name.text = td.name if m != "championship" else "Championship: all %d tracks" % Game.tracks.size()
	var lines: PackedStringArray = [td.subtitle]
	var rec := SaveManager.get_record(tid, m if m != "practice" else "practice")
	if rec.has("best_time"):
		lines.append("Best race (3 laps): %s" % RaceHUD.format_time(float(rec["best_time"])))
	if rec.has("best_lap"):
		lines.append("Best lap: %s" % RaceHUD.format_time(float(rec["best_lap"])))
	if rec.has("best_score"):
		lines.append("Best drift score: %s" % RaceHUD._fmt_points(int(rec["best_score"])))
	lines.append("Surface: %s    Target lap: %s" % [td.surface.capitalize(), RaceHUD.format_time(td.target_lap)])
	_record.text = "\n".join(lines)
	_car_preview.stats = CarStats.build(str(_car1.value()))


func _on_start() -> void:
	Game.players = _players.value()
	Game.mode = _mode.value()
	Game.laps = _laps.value() if Game.mode != "championship" else 3
	Game.view_mode = _view.value()
	SaveManager.set_setting("two_player_view", Game.view_mode)
	SaveManager.set_selected(1, _car1.value())
	if Game.players == 2:
		SaveManager.set_selected(2, _car2.value())
	if Game.mode == "championship":
		Game.start_championship()
	else:
		Game.track_id = _track.value()
	Game.goto("race")
