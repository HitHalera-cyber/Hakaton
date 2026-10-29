class_name RaceManager
extends Node
## Runs one race: builds the world from the session in Game, spawns cars,
## sets up the views (one, split or shared screen), counts laps and
## positions, applies the rules of the selected mode and shows results.

const RIVAL_NAMES := ["NEKO", "BOLT", "VEGA", "MIRA"]
const RIVAL_CARS := ["sport", "retro", "rally", "custom"]
const FINISH_GRACE := 20.0
const COOP_TARGETS := [1500, 3500, 6000]   # team points per lap: bronze/silver/gold

var track_data: TrackData
var track: Track
var world: Node2D
var skids: SkidLayer
var ghost: GhostCar
var cars: Array = []
var humans: Array = []
var racers: Dictionary = {}     # Car -> info Dictionary
var views: LocalMultiplayerManager
var engine_audio: EngineAudio

var mode := "time_attack"
var laps_total := 3
var state := "countdown"
var race_time := 0.0
var shared_view := false

var _countdown := 3.6
var _last_count := 4
var _grace := -1.0
var _finish_order: Array = []
var _ghost_best := 0.0
var _ghost_beaten := false
var _pause: PauseMenu
var _results: ResultsScreen
var _achievement_notes: Array = []


func _ready() -> void:
	mode = Game.mode
	laps_total = 0 if mode == "practice" else Game.laps
	track_data = Game.track_data(Game.track_id)
	shared_view = Game.players == 2 and Game.view_mode == "shared"
	_build_world()
	_spawn_cars()
	_build_views()
	_build_overlays()
	engine_audio = EngineAudio.new()
	add_child(engine_audio)
	for i in humans.size():
		var pan := 0.0 if humans.size() == 1 else (-0.5 if i == 0 else 0.5)
		engine_audio.add_car(humans[i], pan)
	AudioManager.play_music(track_data.music)
	SaveManager.achievement_unlocked.connect(_on_achievement)


func _exit_tree() -> void:
	if SaveManager.achievement_unlocked.is_connected(_on_achievement):
		SaveManager.achievement_unlocked.disconnect(_on_achievement)


func _on_achievement(_id: String, title: String) -> void:
	_achievement_notes.append("Achievement: " + title)


# --- setup --------------------------------------------------------------------

func _build_world() -> void:
	world = Node2D.new()
	world.name = "World"
	track = Track.new()
	track.build(track_data)
	world.add_child(track)
	skids = SkidLayer.new()
	if track_data.surface == "snow":
		skids.mark_color = Color(0.45, 0.5, 0.62)
	world.add_child(skids)
	if mode == "ghost":
		ghost = GhostCar.new()
		world.add_child(ghost)
		if ghost.load_from(SaveManager.load_ghost(track_data.id)):
			_ghost_best = ghost.lap_time
		else:
			ghost.visible = false


func _spawn_cars() -> void:
	var slot := 0
	for p in Game.players:
		var car := _make_car(SaveManager.get_selected(p + 1), slot)
		car.player_index = p + 1
		car.tag_color = Color("ff5fb8") if p == 0 else Color("3ee0ff")
		car.controller = PlayerController.new(p + 1, Game.players == 1)
		humans.append(car)
		slot += 1
	if mode == "championship":
		var rivals := 4 - Game.players
		for r in rivals:
			var rc := _make_car(RIVAL_CARS[r % RIVAL_CARS.size()], slot)
			rc.display_name = RIVAL_NAMES[r]
			rc.tag_color = Color(0.85, 0.85, 0.9)
			var champ_round := int(Game.championship.get("index", 0))
			rc.controller = AutopilotController.new(0.86 + 0.04 * r + 0.02 * champ_round, (r - 1.5) * 5.0, r * 31 + 7)
			slot += 1
	for c in cars:
		racers[c] = {
			"car": c, "name": _car_label(c), "lap": 1, "laps_done": 0, "travelled": 0.0,
			"prev_d": 0.0, "lap_start": 0.0, "last_lap": 0.0, "best_lap": 0.0, "laps": [],
			"finished": false, "finish_time": 0.0, "position": 0, "wrong_t": 0.0, "wrong_way": false,
			"racers": cars.size(), "laps_total": laps_total, "recorder": null,
		}
		var info: Dictionary = racers[c]
		info["prev_d"] = track_data.cum_len[maxi(c.track_idx, 0)]
		info["travelled"] = -(track_data.total_len - float(info["prev_d"])) if float(info["prev_d"]) > track_data.total_len * 0.5 else float(info["prev_d"])
		if mode == "ghost" and c.player_index > 0:
			var rec := GhostCar.Recorder.new()
			rec.start()
			info["recorder"] = rec


func _make_car(car_id: String, slot: int) -> Car:
	var car := Car.new()
	car.night = track.night
	car.setup(CarStats.build(car_id), track_data, skids)
	world.add_child(car)
	var g := track_data.grid_slot(slot)
	car.place(g["position"], g["rotation"])
	car.frozen = true
	car.scoring.enabled = false
	car.crashed.connect(_on_crash.bind(car))
	car.bumped.connect(_on_bump)
	cars.append(car)
	return car


func _car_label(c: Car) -> String:
	if c.player_index > 0:
		return "%dP %s" % [c.player_index, c.stats.name]
	return "%s (%s)" % [c.display_name, c.stats.name]


func _build_views() -> void:
	views = LocalMultiplayerManager.new()
	views.name = "Views"
	add_child(views)
	views.setup(self, world, humans, cars, track_data, ghost, shared_view)


func _build_overlays() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	layer.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(layer)
	_results = ResultsScreen.new()
	layer.add_child(_results)
	_pause = PauseMenu.new()
	layer.add_child(_pause)
	_pause.restart_requested.connect(Game.goto.bind("race"))
	_pause.quit_requested.connect(Game.goto.bind("menu"))


func _on_bump(_other: Car, impact: float) -> void:
	if impact > 60.0:
		AudioManager.play("bump", randf_range(0.9, 1.1), -6.0)


func _on_crash(impact: float, _at: Vector2, car: Car) -> void:
	if car.player_index > 0:
		AudioManager.play("crash", randf_range(0.85, 1.1), linear_to_db(clampf(impact / 160.0, 0.3, 1.0)))


# --- queries used by the HUD --------------------------------------------------

func racer_info(car: Car) -> Dictionary:
	return racers.get(car, {})


func elapsed_for(car: Car) -> float:
	var info: Dictionary = racers.get(car, {})
	if info.get("finished", false):
		return float(info["finish_time"])
	return race_time


func is_over() -> bool:
	return state == "results"


func mode_line(car: Car) -> String:
	match mode:
		"coop":
			var team := 0
			for h in humans:
				team += (h as Car).scoring.total
			return "TEAM %s" % RaceHUD._fmt_points(team)
		"ghost":
			if _ghost_best > 0.0:
				return "GHOST %s" % RaceHUD.format_time(_ghost_best)
			return "SET A LAP TO RACE YOUR GHOST"
		"practice":
			return "PRACTICE — ESC TO LEAVE"
		"drift_attack":
			return "SCORE ATTACK"
	if _grace > 0.0 and not racers[car]["finished"]:
		return "FINISH IN %d" % ceili(_grace)
	return ""


# --- race loop ----------------------------------------------------------------

func _physics_process(delta: float) -> void:
	match state:
		"countdown":
			_tick_countdown(delta)
		"racing":
			race_time += delta
			_tick_racing(delta)
		"results":
			pass


func _tick_countdown(delta: float) -> void:
	_countdown -= delta
	var n := ceili(_countdown)
	if n != _last_count and n <= 3:
		_last_count = n
		if n > 0:
			views.message_all(str(n), Color.WHITE, 0.8)
			AudioManager.play("count")
		else:
			views.message_all("GO!", UiTheme.PINK, 1.0)
			AudioManager.play("go")
			_start_race()


func _start_race() -> void:
	state = "racing"
	race_time = 0.0
	for c in cars:
		(c as Car).frozen = false
		(c as Car).scoring.enabled = true
	if ghost and _ghost_best > 0.0:
		ghost.restart_lap()


func _tick_racing(delta: float) -> void:
	for c in cars:
		_update_progress(c as Car, delta)
	_update_positions()
	if mode == "coop" and humans.size() == 2:
		var a := humans[0] as Car
		var b := humans[1] as Car
		var tandem := a.drifting and b.drifting and a.global_position.distance_to(b.global_position) < 70.0
		a.scoring.tandem = tandem
		b.scoring.tandem = tandem
	views.keep_together(delta, func(c): return racers[c]["travelled"])
	if _grace > 0.0:
		_grace -= delta
		if _grace <= 0.0:
			_end_race()
			return
	if laps_total > 0:
		var all_done := true
		for h in humans:
			if not racers[h]["finished"]:
				all_done = false
		if all_done:
			_end_race()


func _update_progress(car: Car, delta: float) -> void:
	var info: Dictionary = racers[car]
	var rec = info["recorder"]
	if rec != null:
		rec.step(car, delta)
	if info["finished"]:
		return
	var d := track_data.cum_len[maxi(car.track_idx, 0)]
	var step := d - float(info["prev_d"])
	if step < -track_data.total_len * 0.5:
		step += track_data.total_len
	elif step > track_data.total_len * 0.5:
		step -= track_data.total_len
	info["prev_d"] = d
	info["travelled"] = float(info["travelled"]) + step
	# Wrong way: heading against the road for a second.
	var t := track_data.tangents[maxi(car.track_idx, 0)]
	if car.speed > 30.0 and Vector2.from_angle(car.rotation).dot(t) < -0.3 and car.velocity.dot(t) < 0.0:
		info["wrong_t"] = float(info["wrong_t"]) + delta
	else:
		info["wrong_t"] = 0.0
	info["wrong_way"] = float(info["wrong_t"]) > 1.0 and car.player_index > 0
	# Lap completed?
	var done := int(info["laps_done"])
	if float(info["travelled"]) >= (done + 1) * track_data.total_len:
		_complete_lap(car, info)


func _complete_lap(car: Car, info: Dictionary) -> void:
	var lap_time := race_time - float(info["lap_start"])
	info["lap_start"] = race_time
	info["laps_done"] = int(info["laps_done"]) + 1
	info["last_lap"] = lap_time
	(info["laps"] as Array).append(lap_time)
	var best := float(info["best_lap"])
	var is_best := best <= 0.0 or lap_time < best
	if is_best:
		info["best_lap"] = lap_time
	if car.player_index > 0:
		AudioManager.play("lap")
	if mode == "ghost" and car.player_index > 0:
		_ghost_lap(car, info, lap_time)
	if mode == "practice" and car.player_index > 0 and is_best:
		# Practice never "finishes", so its lap record is stored right away.
		SaveManager.submit_record(track_data.id, "practice", {"best_lap": lap_time, "car": car.stats.id})
	if laps_total > 0 and int(info["laps_done"]) >= laps_total:
		info["finished"] = true
		info["finish_time"] = race_time
		_finish_order.append(car)
		car.scoring.bank()
		if car.player_index > 0:
			views.message_for(car, "FINISH!", UiTheme.CYAN, 2.0)
			# The CPU takes the wheel for a cool-down lap.
			car.controller = AutopilotController.new(0.6, 0.0, 3)
		if _grace < 0.0 and cars.size() > 1 and mode in ["versus", "championship", "coop", "time_attack", "drift_attack"]:
			_grace = FINISH_GRACE
	else:
		info["lap"] = int(info["laps_done"]) + 1
		if car.player_index > 0:
			var txt := "LAP %d" % int(info["lap"])
			if laps_total > 0 and int(info["lap"]) == laps_total:
				txt = "FINAL LAP"
			views.message_for(car, txt + ("   BEST!" if is_best and int(info["laps_done"]) > 1 else ""), Color.WHITE, 1.4)


func _ghost_lap(car: Car, info: Dictionary, lap_time: float) -> void:
	var rec = info["recorder"]
	if _ghost_best <= 0.0 or lap_time < _ghost_best:
		if _ghost_best > 0.0:
			_ghost_beaten = true
			views.message_for(car, "GHOST BEATEN!", UiTheme.CYAN, 1.6)
		_ghost_best = lap_time
		SaveManager.save_ghost(track_data.id, GhostCar.to_dict(rec.frames, lap_time, car.stats.id))
		ghost.load_from(SaveManager.load_ghost(track_data.id))
	rec.start()
	ghost.restart_lap()


func _update_positions() -> void:
	var order := cars.duplicate()
	order.sort_custom(func(a, b):
		var ia: Dictionary = racers[a]
		var ib: Dictionary = racers[b]
		if ia["finished"] and ib["finished"]:
			return float(ia["finish_time"]) < float(ib["finish_time"])
		if ia["finished"] != ib["finished"]:
			return ia["finished"]
		return float(ia["travelled"]) > float(ib["travelled"]))
	for i in order.size():
		racers[order[i]]["position"] = i + 1



func _end_race() -> void:
	if state == "results":
		return
	state = "results"
	_pause.can_pause = false
	for c in cars:
		(c as Car).scoring.bank()
		(c as Car).scoring.enabled = false
	var rows: Array = []
	var row_colors: Array = []
	var notes: Array = []
	var ranked := _ranking()
	var winner: Car = ranked[0]
	var any_human_finished := false
	for i in ranked.size():
		var c: Car = ranked[i]
		var info: Dictionary = racers[c]
		var reward := 0
		if c.player_index > 0:
			reward = _reward(c, info, i)
			SaveManager.add_currency(reward)
			_save_records(c, info, notes)
			if info["finished"]:
				any_human_finished = true
		var pts := ""
		if mode == "championship":
			var gained: int = Game.PLACE_POINTS[mini(i, Game.PLACE_POINTS.size() - 1)]
			var table: Dictionary = Game.championship["points"]
			var key := str(info["name"])
			table[key] = int(table.get(key, 0)) + gained
			pts = "+%d (%d)" % [gained, table[key]]
		rows.append([
			"%d." % (i + 1), info["name"],
			RaceHUD.format_time(float(info["finish_time"])) if info["finished"] else "DNF" if laps_total > 0 else "-",
			RaceHUD.format_time(float(info["best_lap"])),
			RaceHUD._fmt_points(c.scoring.total), RaceHUD._fmt_points(c.scoring.best_combo),
			pts if mode == "championship" else ("+%d CR" % reward if reward > 0 else ""),
		])
		row_colors.append(c.tag_color if c.player_index > 0 else UiTheme.DIM)
	if any_human_finished:
		SaveManager.mark_track_finished(track_data.id, Game.tracks.size())
		if humans.size() == 2:
			SaveManager.unlock_achievement("duo")
	if _ghost_beaten:
		SaveManager.unlock_achievement("ghost_buster")
	var title := "RESULTS"
	match mode:
		"coop":
			var team := 0
			for h in humans:
				team += (h as Car).scoring.total
			var per_lap := float(team) / maxf(float(laps_total), 1.0)
			var medal := "NO MEDAL"
			if per_lap >= COOP_TARGETS[2]:
				medal = "GOLD"
			elif per_lap >= COOP_TARGETS[1]:
				medal = "SILVER"
			elif per_lap >= COOP_TARGETS[0]:
				medal = "BRONZE"
			title = "TEAM %s — %s" % [RaceHUD._fmt_points(team), medal]
		"versus", "drift_attack", "championship", "time_attack", "ghost":
			title = "%s WINS!" % (racers[winner]["name"] as String) if cars.size() > 1 else "FINISHED"
	var columns := ["#", "DRIVER", "TIME", "BEST LAP", "DRIFT", "BEST COMBO", "CHAMP" if mode == "championship" else "REWARD"]
	var buttons: Array = []
	if Game.championship_active():
		if int(Game.championship["index"]) + 1 < Game.championship["tracks"].size():
			buttons.append(["Next race", _next_championship_race])
		else:
			notes.append_array(_championship_final())
			buttons.append(["Menu", Game.goto.bind("menu")])
	else:
		buttons.append(["Race again", Game.goto.bind("race")])
		buttons.append(["Setup", Game.goto.bind("setup")])
		buttons.append(["Garage", Game.goto.bind("garage")])
		buttons.append(["Menu", Game.goto.bind("menu")])
	notes.append_array(_achievement_notes)
	var sub := "%s · %s · %s" % [track_data.name, Game.mode_name(mode), "%d laps" % laps_total if laps_total > 0 else "free run"]
	_results.show_results({
		"title": title, "subtitle": sub, "columns": columns, "rows": rows,
		"row_colors": row_colors, "notes": notes, "buttons": buttons,
	})


func _next_championship_race() -> void:
	Game.advance_championship()
	Game.goto("race")


func _ranking() -> Array:
	var order := cars.duplicate()
	match mode:
		"drift_attack", "coop", "practice":
			order.sort_custom(func(a, b): return (a as Car).scoring.total > (b as Car).scoring.total)
		_:
			order.sort_custom(func(a, b): return int(racers[a]["position"]) < int(racers[b]["position"]))
	return order


func _reward(c: Car, info: Dictionary, place: int) -> int:
	var r := int(c.scoring.total / 40)
	if info["finished"]:
		r += 50
	if cars.size() > 1 and mode != "coop":
		r += [150, 90, 50, 20][mini(place, 3)]
	if mode == "time_attack" and info["finished"] and laps_total > 0:
		if float(info["best_lap"]) <= track_data.target_lap:
			r += 100
	return r


func _save_records(c: Car, info: Dictionary, notes: Array) -> void:
	var result := {
		"time": float(info["finish_time"]) if info["finished"] and laps_total > 0 else 0.0,
		"best_lap": float(info["best_lap"]),
		"score": c.scoring.total,
		"best_combo": c.scoring.best_combo,
		"car": c.stats.id,
	}
	var key_mode := mode if laps_total == 0 or laps_total == 3 else "%s_%d" % [mode, laps_total]
	var improved := SaveManager.submit_record(track_data.id, key_mode, result)
	for f in improved:
		match f:
			"time":
				notes.append("%dP: new best race time!" % c.player_index)
			"lap":
				notes.append("%dP: new best lap!" % c.player_index)
			"score":
				notes.append("%dP: new drift record!" % c.player_index)
	SaveManager.add_stats(c.scoring.total, c.scoring.best_combo, c.distance_driven)
	if c.scoring.drifts_banked > 0:
		SaveManager.unlock_achievement("first_drift")
	if c.scoring.best_combo >= 3000:
		SaveManager.unlock_achievement("combo_3k")
	if c.scoring.best_combo >= 10000:
		SaveManager.unlock_achievement("combo_10k")


func _championship_final() -> Array:
	var table: Dictionary = Game.championship["points"]
	var names := table.keys()
	names.sort_custom(func(a, b): return int(table[a]) > int(table[b]))
	var out: Array = ["CHAMPIONSHIP STANDINGS:"]
	for i in names.size():
		out.append("%d. %s — %d pts" % [i + 1, names[i], int(table[names[i]])])
	if not names.is_empty() and (str(names[0]).begins_with("1P") or str(names[0]).begins_with("2P")):
		SaveManager.unlock_achievement("champion")
		SaveManager.add_currency(500)
		out.append("Champion bonus: +500 CR")
	Game.championship = {}
	return out
