extends Control
## Race setup: players, mode, track, laps, split/shared view and car choice.

var _players: Widgets.OptionCycler
var _mode: Widgets.OptionCycler
var _track: Widgets.OptionCycler
var _laps: Widgets.OptionCycler
var _dir: Widgets.OptionCycler
var _view: Widgets.OptionCycler
var _car1: Widgets.OptionCycler
var _car2: Widgets.OptionCycler
var _bots: Widgets.OptionCycler
var _skill: Widgets.OptionCycler
var _role1: Widgets.OptionCycler
var _role2: Widgets.OptionCycler
var _cops: Widgets.OptionCycler
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

	# The option list scrolls when a mode needs many rows.
	var scroll := ScrollContainer.new()
	scroll.position = Vector2(40, 80)
	scroll.size = Vector2(452, 328)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	add_child(scroll)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 4)
	scroll.add_child(col)

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
	_dir = Widgets.OptionCycler.new("DIRECTION", ["Normal", "Reverse"], [false, true], 1 if Game.reverse else 0)
	_dir.changed.connect(func(_v): _refresh_info())
	col.add_child(_dir)
	_laps = Widgets.OptionCycler.new("LAPS", ["1", "2", "3", "4", "5"], [1, 2, 3, 4, 5], Game.laps - 1)
	col.add_child(_laps)
	_role1 = Widgets.OptionCycler.new("1P ROLE", ["Robber", "Cop"], ["robber", "cop"], 1 if Game.roles[0] == "cop" else 0)
	col.add_child(_role1)
	_role2 = Widgets.OptionCycler.new("2P ROLE", ["Robber", "Cop"], ["robber", "cop"], 1 if Game.roles[1] == "cop" else 0)
	col.add_child(_role2)
	_cops = Widgets.OptionCycler.new("COPS", ["1", "2", "3", "4", "5", "6"], [1, 2, 3, 4, 5, 6], Game.cops - 1)
	col.add_child(_cops)
	_bots = Widgets.OptionCycler.new("BOTS", ["0", "1", "2", "3", "4", "5"], [0, 1, 2, 3, 4, 5], Game.bots)
	col.add_child(_bots)
	_skill = Widgets.OptionCycler.new("BOT LEVEL", ["Rookie", "Pro", "Ace"], [0, 1, 2], Game.bot_skill)
	col.add_child(_skill)
	_view = Widgets.OptionCycler.new("2P SCREEN", ["Split screen", "Shared camera"], ["split", "shared"],
			0 if Game.view_mode == "split" else 1)
	col.add_child(_view)
	_car1 = Widgets.OptionCycler.new("1P CAR", [], [])
	_car1.changed.connect(func(_v): _refresh_info())
	col.add_child(_car1)
	_car2 = Widgets.OptionCycler.new("2P CAR", [], [])
	col.add_child(_car2)
	_fill_cars()

	_desc = UiTheme.label("", 12, UiTheme.DIM)
	_desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_desc.position = Vector2(40, 410)
	_desc.size = Vector2(460, 56)
	add_child(_desc)

	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 10)
	buttons.position = Vector2(40, 476)
	add_child(buttons)
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
	_preview.size = Vector2(400, 180)
	add_child(_preview)
	_record = UiTheme.label("", 13, UiTheme.CYAN)
	_record.position = Vector2(520, 306)
	_record.size = Vector2(236, 230)
	_record.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_record)
	_car_preview = Widgets.CarPreview.new()
	_car_preview.position = Vector2(764, 330)
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
	_desc.text = tr(Game.MODES[m]["desc"])
	var arena: bool = m in ["gymkhana", "training"]
	var city: bool = m in RaceManager.CITY_MODES or RaceManager.FIELD_MODES.has(m)
	_laps.visible = not (m in ["practice", "championship", "gymkhana", "training", "tandem", "elimination"] or city)
	_track.visible = not (arena or city)
	var tid: String = "arena" if arena else (("city" if m in RaceManager.CITY_MODES else str(RaceManager.FIELD_MODES.get(m, "city"))) if city else str(_track.value()))
	var rev: bool = _dir.value() and m != "championship" and not city
	_dir.visible = not (m in ["championship", "gymkhana", "training"] or city)
	_bots.visible = m in RaceManager.BOT_MODES or (city and m != "police")
	_skill.visible = _bots.visible or m == "police"
	_role1.visible = m == "police"
	_role2.visible = m == "police" and _players.value() == 2
	_cops.visible = m == "police"
	var td := Game.track_data(tid, rev)
	_preview.set_track(td)
	if m == "championship":
		var names: PackedStringArray = []
		for c in Game.cup_tracks(tid):
			names.append(str(Game.track_def(c)["name"]))
		_track_name.text = tr("Cup %d") % (Game.track_ids().find(tid) / 4 + 1) + ": " + ", ".join(names)
	else:
		_track_name.text = td.name
	var lines: PackedStringArray = [tr(td.subtitle)]
	var rec := SaveManager.get_record(td.id, m if m != "practice" else "practice")
	if rec.has("best_time"):
		lines.append(tr("Best race (3 laps): %s") % RaceHUD.format_time(float(rec["best_time"])))
	if rec.has("best_lap"):
		lines.append(tr("Best lap: %s") % RaceHUD.format_time(float(rec["best_lap"])))
	if rec.has("best_score"):
		lines.append(tr("Best drift score: %s") % RaceHUD._fmt_points(int(rec["best_score"])))
	if not td.arena:
		lines.append(tr("Surface: %s    Target lap: %s") % [tr(td.surface.capitalize()), RaceHUD.format_time(td.target_lap)])
	if not city and m != "elimination":
		var st := SaveManager.get_stars(td.id)
		var texts := RaceManager.star_texts(td.arena)
		var n := 0
		for k in 3:
			n += 1 if st[k] else 0
		lines.append(tr("Stars %d/3") % n + ":")
		for k in 3:
			lines.append(("  [x] " if st[k] else "  [ ] ") + tr(texts[k]))
	_record.text = "\n".join(lines)
	_car_preview.stats = CarStats.build(str(_car1.value()))


func _on_start() -> void:
	Game.players = _players.value()
	Game.mode = _mode.value()
	Game.laps = _laps.value() if Game.mode != "championship" else 3
	Game.view_mode = _view.value()
	Game.bots = _bots.value()
	Game.bot_skill = _skill.value()
	Game.roles = [_role1.value(), _role2.value()]
	Game.cops = _cops.value()
	SaveManager.set_setting("two_player_view", Game.view_mode)
	SaveManager.set_selected(1, _car1.value())
	if Game.players == 2:
		SaveManager.set_selected(2, _car2.value())
	if Game.mode == "championship":
		Game.start_championship(_track.value())
	else:
		Game.track_id = _track.value()
		Game.reverse = _dir.value()
	Game.goto("race")
