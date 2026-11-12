class_name RaceManager
extends Node
## Runs one race: builds the world from the session in Game, spawns cars,
## sets up the views (one, split or shared screen), counts laps and
## positions, applies the rules of the selected mode and shows results.

const RIVAL_NAMES := ["NEKO", "BOLT", "VEGA", "MIRA", "ZED", "KIRA", "RYU", "SOL"]
const RIVAL_CARS := ["sport", "retro", "rally", "custom", "jdm", "classic"]
## Modes on the city map, and the track modes where bots can join.
const CITY_MODES := ["police", "bomb"]
const BOT_MODES := ["time_attack", "drift_attack", "practice", "versus", "coop", "elimination"]
const BOT_SKILL := [0.82, 0.92, 1.02]
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
var day_cycle: DayCycle
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
const GYMKHANA_TIME := 90.0
var gyms: Dictionary = {}           # Car -> Gymkhana (arena modes)
var training: TrainingDirector
var tandem_round := 1
var tandem_leader := 0              # index into humans
# Best-drift replay: every car's pose is recorded each physics tick.
const REPLAY_SPEED := 0.35
const REC_MAX := 72000                 # 20 minutes at 60 Hz
var _rec_t := PackedFloat32Array()
var _rec: Dictionary = {}              # Car -> CarTape


## One car's recorded poses. Packed arrays as members are changed in place
## (inside a Dictionary they would be copied on every append).
class CarTape:
	var pos := PackedVector2Array()
	var rot := PackedFloat32Array()
	var slip := PackedFloat32Array()

var _rf := 0
var _rf_end := 0
var _replay_car: Car
var photo: PhotoMode
var game: RefCounted                 # PoliceChase / HotPotato / Elimination
var _cash_layer: Node2D


func _ready() -> void:
	mode = Game.mode
	laps_total = 0 if mode in ["practice", "gymkhana", "training", "tandem", "elimination"] + CITY_MODES else Game.laps
	if mode in ["gymkhana", "training"]:
		track_data = Game.track_data("arena")
	elif mode in CITY_MODES:
		track_data = Game.track_data("city")
	else:
		track_data = Game.track_data(Game.track_id, Game.reverse)
	# The city is too big for one shared camera: always split there.
	shared_view = Game.players == 2 and Game.view_mode == "shared" and not (mode in CITY_MODES)
	_build_world()
	_spawn_cars()
	_build_views()
	_build_overlays()
	track.spectators.cars = cars
	_setup_game()
	if mode in ["gymkhana", "training"]:
		for h in humans:
			gyms[h] = Gymkhana.new(h, track_data.posts)
		if mode == "training":
			training = TrainingDirector.new(humans[0], gyms[humans[0]])
	day_cycle = DayCycle.new()
	add_child(day_cycle)
	day_cycle.setup(self, track, views)
	engine_audio = EngineAudio.new()
	add_child(engine_audio)
	for i in humans.size():
		var pan := 0.0 if humans.size() == 1 else (-0.5 if i == 0 else 0.5)
		engine_audio.add_car(humans[i], pan)
	AudioManager.play_music(track_data.music)
	SaveManager.achievement_unlocked.connect(_on_achievement)


func _exit_tree() -> void:
	Engine.time_scale = 1.0
	if SaveManager.achievement_unlocked.is_connected(_on_achievement):
		SaveManager.achievement_unlocked.disconnect(_on_achievement)


func _on_achievement(_id: String, title: String) -> void:
	_achievement_notes.append(tr("Achievement: ") + tr(title))


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
	if track_data.city:
		_spawn_city()
		return
	var slot := 0
	for p in Game.players:
		# In tandem the chaser (2P) starts one row behind the leader.
		var car := _make_car(SaveManager.get_selected(p + 1), 2 if mode == "tandem" and p == 1 else slot)
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
			var ai := AutopilotController.new(0.86 + 0.04 * r + 0.02 * champ_round, (r - 1.5) * 5.0, r * 31 + 7)
			# Rivals show off big drifts on asphalt; on dirt and snow they stay tidier.
			ai.drift_happy = 0.9 if track_data.surface in ["asphalt", "wet"] else 0.6
			rc.controller = ai
			slot += 1
	elif mode in BOT_MODES:
		var n := Game.bots
		if mode == "elimination":
			n = maxi(n, 4 - Game.players)
		for r in n:
			_add_bot(r, slot)
			slot += 1
	_init_racers()


func _add_bot(r: int, slot: int) -> Car:
	var rc := _make_car(RIVAL_CARS[r % RIVAL_CARS.size()], slot)
	rc.display_name = RIVAL_NAMES[r % RIVAL_NAMES.size()]
	rc.tag_color = Color(0.85, 0.85, 0.9)
	var skill: float = BOT_SKILL[clampi(Game.bot_skill, 0, 2)] + 0.02 * (r % 3)
	var ai := AutopilotController.new(skill, (r % 4 - 1.5) * 6.0, r * 31 + 7)
	ai.drift_happy = 0.9 if track_data.surface in ["asphalt", "wet"] else 0.6
	rc.controller = ai
	return rc


## City modes: humans pick robber or cop; bots fill the other places.
func _spawn_city() -> void:
	var d := track_data
	var cops_spots := [d.node_index(0, 0), d.node_index(7, 5), d.node_index(7, 0), d.node_index(0, 5),
			d.node_index(0, 2), d.node_index(7, 3), d.node_index(3, 0), d.node_index(4, 5)]
	var mid_spots := [d.node_index(3, 2), d.node_index(4, 3), d.node_index(4, 2), d.node_index(3, 3)]
	for p in Game.players:
		var car := _make_car(SaveManager.get_selected(p + 1), 0)
		car.player_index = p + 1
		car.tag_color = Color("ff5fb8") if p == 0 else Color("3ee0ff")
		car.controller = PlayerController.new(p + 1, Game.players == 1)
		humans.append(car)
	var skill: float = [0.8, 0.88, 0.96][clampi(Game.bot_skill, 0, 2)]
	if mode == "police":
		var robbers: Array = []
		var cop_cars: Array = []
		for k in humans.size():
			if str(Game.roles[k]) == "cop":
				cop_cars.append(humans[k])
			else:
				robbers.append(humans[k])
		if robbers.is_empty():
			var rb := _make_car("jdm", 0)
			rb.display_name = "ROBBER"
			rb.tag_color = Color("7dff8a")
			# The getaway driver is a bit quicker than the patrol cars.
			rb.controller = CityDriver.new(d, 5, skill + 0.1)
			robbers.append(rb)
		var bot_cops := maxi(Game.cops - cop_cars.size(), 0)
		for k in bot_cops:
			var cc := _make_car("sport" if k % 2 == 0 else "classic", 0)
			cc.display_name = "COP %d" % (k + 1)
			cc.tag_color = Color("6aa0ff")
			cc.controller = CityDriver.new(d, k * 13 + 3, skill)
			cop_cars.append(cc)
		for c in cop_cars:
			(c as Car).stats.color = Color("f2f2f2")
			(c as Car).stats.decal = 1
		for k in robbers.size():
			_place_at_node(robbers[k], mid_spots[k % mid_spots.size()])
		for k in cop_cars.size():
			_place_at_node(cop_cars[k], cops_spots[k % cops_spots.size()])
		var pc := PoliceChase.new()
		game = pc
		_init_racers()
		pc.setup(self, robbers, cop_cars)
	else:
		for k in maxi(Game.bots, 4 - Game.players):
			var bc := _make_car(RIVAL_CARS[k % RIVAL_CARS.size()], 0)
			bc.display_name = RIVAL_NAMES[k % RIVAL_NAMES.size()]
			bc.tag_color = Color(0.85, 0.85, 0.9)
			bc.controller = CityDriver.new(d, k * 17 + 1, skill)
		var spots := [d.node_index(1, 1), d.node_index(6, 4), d.node_index(6, 1), d.node_index(1, 4),
				d.node_index(3, 2), d.node_index(4, 3), d.node_index(3, 5), d.node_index(4, 0)]
		for k in cars.size():
			_place_at_node(cars[k], spots[k % spots.size()])
		var hp := HotPotato.new()
		game = hp
		_init_racers()
		hp.setup(self, cars)


func _setup_game() -> void:
	if mode == "elimination":
		var el := Elimination.new()
		el.setup(self, cars)
		game = el
	if game is PoliceChase:
		_cash_layer = Node2D.new()
		_cash_layer.z_index = 4
		world.add_child(_cash_layer)
		_cash_layer.draw.connect(func(): (game as PoliceChase).draw_cash(_cash_layer))


## Takes a car out of the game (busted, blown up, eliminated). hide: also
## remove it from the screen (on a race track it would block the road).
func knock_out(c: Car, hide: bool) -> void:
	c.scoring.bank()
	c.scoring.enabled = false
	c.out = true
	c.frozen = true
	c.siren = false
	c.collision_layer = 0
	c.collision_mask = 0
	c.modulate = Color(0.45, 0.45, 0.5, 0.8)
	if hide:
		c.visible = false
	racers[c]["out_at"] = race_time


func short_name(c: Car) -> String:
	return "%dP" % c.player_index if c.player_index > 0 else c.display_name


func _place_at_node(c: Car, n: int) -> void:
	var nb: Array = track_data.links[n]
	var to: Vector2 = track_data.nodes[int(nb[0])]
	c.place(track_data.nodes[n], (to - track_data.nodes[n]).angle())
	c._update_track()


func _init_racers() -> void:
	for c in cars:
		racers[c] = {
			"car": c, "name": _car_label(c), "lap": 1, "laps_done": 0, "travelled": 0.0,
			"prev_d": 0.0, "lap_start": 0.0, "last_lap": 0.0, "best_lap": 0.0, "laps": [],
			"finished": false, "finish_time": 0.0, "position": 0, "wrong_t": 0.0, "wrong_way": false,
			"racers": cars.size(), "laps_total": laps_total, "recorder": null,
		}
		var info: Dictionary = racers[c]
		_reset_progress(c, info)
		if mode == "ghost" and c.player_index > 0:
			var rec := GhostCar.Recorder.new()
			rec.start()
			info["recorder"] = rec


func _reset_progress(c: Car, info: Dictionary) -> void:
	info["prev_d"] = track_data.cum_len[maxi(c.track_idx, 0)]
	info["travelled"] = -(track_data.total_len - float(info["prev_d"])) if float(info["prev_d"]) > track_data.total_len * 0.5 else float(info["prev_d"])
	info["laps_done"] = 0
	info["lap"] = 1
	info["lap_start"] = race_time


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
	car.boosted.connect(_on_boost.bind(car))
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
	photo = PhotoMode.new()
	photo.race = self
	layer.add_child(photo)
	_pause.photo_requested.connect(photo.open)


func _on_boost(level: int, car: Car) -> void:
	if car.player_index > 0:
		AudioManager.play("go", 1.1 + level * 0.15, -6.0)


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
	return state in ["results", "replay"]


func mode_line(car: Car) -> String:
	if game:
		return game.mode_line(car)
	match mode:
		"gymkhana":
			var g: Gymkhana = gyms.get(car)
			return tr("TIME %d   DONUTS %d   EIGHTS %d") % [ceili(maxf(GYMKHANA_TIME - race_time, 0.0)), g.donuts, g.eights]
		"training":
			return tr("TRAINING")
		"tandem":
			var lead := humans[tandem_leader] as Car
			if car == lead:
				return tr("ROUND %d — YOU LEAD") % tandem_round
			return tr("ROUND %d — CHASE! %d px") % [tandem_round, int(car.global_position.distance_to(lead.global_position))]
		"coop":
			var team := 0
			for h in humans:
				team += (h as Car).scoring.total
			return tr("TEAM %s") % RaceHUD._fmt_points(team)
		"ghost":
			if _ghost_best > 0.0:
				return tr("GHOST %s") % RaceHUD.format_time(_ghost_best)
			return tr("SET A LAP TO RACE YOUR GHOST")
		"practice":
			return tr("PRACTICE — ESC TO LEAVE")
		"drift_attack":
			return tr("SCORE ATTACK")
	if _grace > 0.0 and not racers[car]["finished"]:
		return tr("FINISH IN %d") % ceili(_grace)
	return ""


# --- race loop ----------------------------------------------------------------

func _physics_process(delta: float) -> void:
	match state:
		"countdown":
			_tick_countdown(delta)
		"racing":
			race_time += delta
			_record()
			_tick_racing(delta)
		"replay":
			_tick_replay()
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
			views.message_all(tr("GO!"), UiTheme.PINK, 1.0)
			AudioManager.play("go")
			_start_race()


func _start_race() -> void:
	var first := race_time == 0.0
	state = "racing"
	for c in cars:
		(c as Car).frozen = false
		(c as Car).scoring.enabled = true
	if ghost and _ghost_best > 0.0:
		ghost.restart_lap()
	# Teach the core mechanic in the first races.
	if first and mode != "training" and int(SaveManager.data["stats"]["races"]) < 5:
		for h in humans:
			views.message_for(h, tr("Handbrake into corners to drift! Drifting charges a BOOST."), UiTheme.CYAN, 5.0, false)


func _tick_racing(delta: float) -> void:
	for c in cars:
		_update_progress(c as Car, delta)
	_update_positions()
	for g in gyms.values():
		(g as Gymkhana).update(delta)
	if mode == "gymkhana" and race_time >= GYMKHANA_TIME:
		_end_race()
		return
	if game:
		game.tick(delta)
		if _cash_layer:
			_cash_layer.queue_redraw()
		if game.is_done():
			_end_race()
			return
	if training:
		if training.update(delta):
			AudioManager.play("lap")
			views.message_all(tr("GOOD!"), UiTheme.CYAN, 1.0)
		for h in views.huds:
			(h as RaceHUD).hint = training.hint()
	if mode == "tandem" and humans.size() == 2:
		_tandem_tick(delta)
	if mode == "coop" and humans.size() == 2:
		var a := humans[0] as Car
		var b := humans[1] as Car
		var tandem := a.drifting and b.drifting and a.global_position.distance_to(b.global_position) < 70.0
		a.scoring.tandem = tandem
		b.scoring.tandem = tandem
	if not track_data.city:
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
	info["wrong_way"] = float(info["wrong_t"]) > 1.0 and car.player_index > 0 and not track_data.arena
	# Lap completed?
	var done := int(info["laps_done"])
	if float(info["travelled"]) >= (done + 1) * track_data.total_len:
		_complete_lap(car, info)


## Tandem: the chaser scores for drifting close behind the drifting leader.
func _tandem_tick(_delta: float) -> void:
	var lead := humans[tandem_leader] as Car
	var chase := humans[1 - tandem_leader] as Car
	var d := lead.global_position.distance_to(chase.global_position)
	var close := d < 80.0 and chase.drifting and lead.drifting
	chase.scoring.tandem = close
	lead.scoring.tandem = false
	if close:
		# Extra chase points on top of the normal drift chain.
		chase.scoring.current += 260.0 * (1.0 - d / 80.0) * get_physics_process_delta_time()


func _tandem_round_over() -> void:
	for c in cars:
		(c as Car).scoring.bank()
	if tandem_round >= 2:
		_end_race()
		return
	tandem_round += 1
	tandem_leader = 1 - tandem_leader
	# Swap places on the grid and restart with a countdown.
	var slots := {humans[tandem_leader]: 0, humans[1 - tandem_leader]: 2}
	for h in humans:
		var car := h as Car
		var g := track_data.grid_slot(int(slots[car]))
		car.global_position = g["position"]
		car.rotation = g["rotation"]
		car.velocity = Vector2.ZERO
		car.respawn_soft()
		car.frozen = true
		_reset_progress(car, racers[car])
	state = "countdown"
	_countdown = 3.6
	_last_count = 4
	views.message_all(tr("ROLES SWAP!"), UiTheme.PINK, 2.0)


func _complete_lap(car: Car, info: Dictionary) -> void:
	if track_data.arena:
		return
	if mode == "tandem":
		info["laps_done"] = int(info["laps_done"]) + 1
		if car == humans[tandem_leader]:
			_tandem_round_over()
		return
	var lap_time := race_time - float(info["lap_start"])
	info["lap_start"] = race_time
	# Clean lap: no barrier touched since the last line crossing.
	if car.player_index > 0 and int(info["laps_done"]) > 0 and car.touches == int(info.get("touch0", 0)):
		info["clean_lap"] = true
	info["touch0"] = car.touches
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
			views.message_for(car, tr("FINISH!"), UiTheme.CYAN, 2.0)
			# The CPU takes the wheel for a cool-down lap.
			car.controller = AutopilotController.new(0.6, 0.0, 3)
		if _grace < 0.0 and cars.size() > 1 and mode in ["versus", "championship", "coop", "time_attack", "drift_attack"]:
			_grace = FINISH_GRACE
	else:
		info["lap"] = int(info["laps_done"]) + 1
		if car.player_index > 0:
			var txt := tr("LAP %d") % int(info["lap"])
			if laps_total > 0 and int(info["lap"]) == laps_total:
				txt = tr("FINAL LAP")
			views.message_for(car, txt + (tr("   BEST!") if is_best and int(info["laps_done"]) > 1 else ""), Color.WHITE, 1.4)


func _ghost_lap(car: Car, info: Dictionary, lap_time: float) -> void:
	var rec = info["recorder"]
	if _ghost_best <= 0.0 or lap_time < _ghost_best:
		if _ghost_best > 0.0:
			_ghost_beaten = true
			views.message_for(car, tr("GHOST BEATEN!"), UiTheme.CYAN, 1.6)
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
	if state in ["results", "replay"]:
		return
	_pause.can_pause = false
	for c in cars:
		(c as Car).scoring.bank()
		(c as Car).scoring.enabled = false
	if not _begin_replay():
		_show_results()


# --- best-drift replay ----------------------------------------------------------

func _record() -> void:
	if _rec_t.size() >= REC_MAX:
		return
	_rec_t.append(race_time)
	for c in cars:
		var car := c as Car
		car.scoring.clock = race_time
		if not _rec.has(car):
			_rec[car] = CarTape.new()
		var r: CarTape = _rec[car]
		r.pos.append(car.global_position)
		r.rot.append(car.rotation)
		r.slip.append(car.slip_deg if car.drifting else -1.0)


func _frame_at(t: float) -> int:
	return clampi(_rec_t.bsearch(t), 0, _rec_t.size() - 1)


## Plays the best combo of the race in slow motion; false if there is none.
func _begin_replay() -> bool:
	var best: Car = null
	for h in humans:
		if best == null or (h as Car).scoring.best_combo > best.scoring.best_combo:
			best = h
	if best == null or best.scoring.best_combo < 500 or _rec_t.size() < 60 or not SaveManager.get_setting("replays", true):
		return false
	var w := best.scoring.best_window
	_rf = _frame_at(maxf(w.x - 1.0, w.y - 7.0))
	_rf_end = _frame_at(w.y + 0.6)
	if _rf_end - _rf < 40:
		return false
	state = "replay"
	_replay_car = best
	if ghost:
		ghost.visible = false
	for c in cars:
		var car := c as Car
		car.replaying = true
		car.boost_t = 0.0
		car.air_t = 0.0
		_apply_frame(car, _rf)
		car._snap_interpolation()
	for cam in views.cameras:
		(cam as CameraController).targets = [best]
		(cam as CameraController).snap_to_targets()
	views.message_all(tr("REPLAY"), UiTheme.PINK, 1.5)
	var label := tr("Best drift %s: %s · Enter — skip") % ["%dP" % best.player_index, RaceHUD._fmt_points(best.scoring.best_combo)]
	for h in views.huds:
		(h as RaceHUD).hint = label
	Engine.time_scale = REPLAY_SPEED
	return true


func _apply_frame(car: Car, f: int) -> void:
	var r: CarTape = _rec.get(car)
	if r == null or f >= r.pos.size():
		return
	var pos := r.pos
	car.global_position = pos[f]
	car.rotation = r.rot[f]
	var slip: float = r.slip[f]
	car.drifting = slip >= 0.0
	car.slip_deg = maxf(slip, 0.0)
	car.velocity = (pos[f] - pos[maxi(f - 1, 0)]) * 60.0
	car.speed = car.velocity.length()


func _tick_replay() -> void:
	_rf += 1
	for c in cars:
		var car := c as Car
		car._snap_interpolation()
		_apply_frame(car, _rf)
	if _rf >= _rf_end:
		_finish_replay()


func _finish_replay() -> void:
	if state != "replay":
		return
	Engine.time_scale = 1.0
	for c in cars:
		(c as Car).replaying = false
		(c as Car).frozen = true
	for h in views.huds:
		(h as RaceHUD).hint = ""
		(h as RaceHUD).show_message("", Color.WHITE, 0.0)
	_show_results()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and (event as InputEventKey).keycode == KEY_F2:
		if state in ["racing", "countdown", "replay"] and not get_tree().paused:
			photo.open()
			get_viewport().set_input_as_handled()
			return
	if state == "replay" and (event.is_action_pressed("ui_accept") or event.is_action_pressed("pause")):
		get_viewport().set_input_as_handled()
		_finish_replay()


func _show_results() -> void:
	state = "results"
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
			_time_cell(c, info),
			RaceHUD.format_time(float(info["best_lap"])),
			RaceHUD._fmt_points(c.scoring.total), RaceHUD._fmt_points(c.scoring.best_combo),
			pts if mode == "championship" else ("+%d CR" % reward if reward > 0 else ""),
		])
		row_colors.append(c.tag_color if c.player_index > 0 else UiTheme.DIM)
	if any_human_finished:
		SaveManager.mark_track_finished(Game.track_id, Game.tracks.size())
		if humans.size() == 2:
			SaveManager.unlock_achievement("duo")
	if _ghost_beaten:
		SaveManager.unlock_achievement("ghost_buster")
	_duel_notes(ranked, notes)
	var title := tr("RESULTS")
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
			title = tr("TEAM %s — %s") % [RaceHUD._fmt_points(team), tr(medal)]
		"versus", "drift_attack", "championship", "time_attack", "ghost":
			title = tr("%s WINS!") % (racers[winner]["name"] as String) if cars.size() > 1 else tr("FINISHED")
		"police", "bomb", "elimination":
			title = game.title()
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
	var sub := "%s · %s" % [tr(track_data.name), tr(Game.mode_name(mode))]
	if game == null:
		sub += " · " + (tr("%d laps") % laps_total if laps_total > 0 else tr("free run"))
	_results.show_results({
		"title": title, "subtitle": sub, "columns": columns, "rows": rows,
		"row_colors": row_colors, "notes": notes, "buttons": buttons,
	})


## 1P against 2P: who placed higher, saved to the duel table.
func _duel_notes(ranked: Array, notes: Array) -> void:
	if humans.size() != 2 or mode in ["coop", "practice", "training"]:
		return
	var a := humans[0] as Car
	var b := humans[1] as Car
	var by_score: bool = mode in ["drift_attack", "gymkhana", "tandem", "police"]
	var winner := 0 if ranked.find(a) < ranked.find(b) else 1
	if game is PoliceChase:
		# Different sides: the side that won the chase wins the duel.
		var pc := game as PoliceChase
		var a_cop: bool = a in pc.cops
		if a_cop != (b in pc.cops):
			winner = 0 if a_cop == (pc.winner == "cops") else 1
	if by_score and a.scoring.total == b.scoring.total and not (game is PoliceChase and (a in (game as PoliceChase).cops) != (b in (game as PoliceChase).cops)):
		winner = -1
	var line := ""
	if by_score or laps_total == 0:
		line = "1P %s — 2P %s" % [RaceHUD._fmt_points(a.scoring.total), RaceHUD._fmt_points(b.scoring.total)]
	else:
		var ta := RaceHUD.format_time(float(racers[a]["finish_time"])) if racers[a]["finished"] else tr("DNF")
		var tb := RaceHUD.format_time(float(racers[b]["finish_time"])) if racers[b]["finished"] else tr("DNF")
		line = "1P %s — 2P %s" % [ta, tb]
	SaveManager.record_duel(track_data.id, mode, winner, line)
	if Game.championship_active():
		var cd: Array = Game.championship.get("duel", [0, 0])
		if winner >= 0:
			cd[winner] = int(cd[winner]) + 1
		Game.championship["duel"] = cd
	var w := SaveManager.duel_wins()
	var head := tr("DRAW") if winner < 0 else tr("%dP WINS THE DUEL") % (winner + 1)
	notes.append(tr("DUEL: %s (%s) · overall 1P %d : %d 2P") % [head, line, w[0], w[1]])


func _time_cell(c: Car, info: Dictionary) -> String:
	if info.has("out_at"):
		return tr("OUT %s") % RaceHUD.format_time(float(info["out_at"]))
	if game is PoliceChase:
		return tr("COP") if c in (game as PoliceChase).cops else tr("FREE")
	if game:
		return tr("ALIVE")
	if info["finished"]:
		return RaceHUD.format_time(float(info["finish_time"]))
	return tr("DNF") if laps_total > 0 else "-"


func _next_championship_race() -> void:
	Game.advance_championship()
	Game.goto("race")


func _ranking() -> Array:
	var order := cars.duplicate()
	if mode in ["bomb", "elimination"]:
		# Survivors first, then by how long each car lasted.
		order.sort_custom(func(a, b):
			var oa: float = racers[a].get("out_at", INF)
			var ob: float = racers[b].get("out_at", INF)
			if oa != ob:
				return oa > ob
			if mode == "elimination":
				return int(racers[a]["position"]) < int(racers[b]["position"])
			return (a as Car).scoring.total > (b as Car).scoring.total)
		return order
	match mode:
		"drift_attack", "coop", "practice", "gymkhana", "tandem", "training", "police":
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


## The three challenge stars of a track. Arena modes have their own set.
static func star_texts(arena: bool) -> Array:
	if arena:
		return ["Finish a gymkhana run", "3 donuts in one run", "A figure eight"]
	return ["Finish a race", "Grade S in 5 drift zones in one race", "A clean lap: no barrier touched"]


func _check_stars(c: Car, info: Dictionary, notes: Array) -> void:
	if track_data.city or mode == "elimination":
		return
	var got: Array = [false, false, false]
	if track_data.arena:
		var g: Gymkhana = gyms.get(c)
		got = [mode == "gymkhana", g != null and g.donuts >= 3, g != null and g.eights >= 1]
	else:
		got = [bool(info["finished"]) or (mode == "tandem"), c.scoring.zones_s >= 5, bool(info.get("clean_lap", false))]
	var texts := star_texts(track_data.arena)
	for k in 3:
		if got[k] and SaveManager.award_star(track_data.id, k):
			notes.append(tr("NEW STAR: %s") % tr(texts[k]))


func _save_records(c: Car, info: Dictionary, notes: Array) -> void:
	_check_stars(c, info, notes)
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
				notes.append(tr("%dP: new best race time!") % c.player_index)
			"lap":
				notes.append(tr("%dP: new best lap!") % c.player_index)
			"score":
				notes.append(tr("%dP: new drift record!") % c.player_index)
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
	var out: Array = [tr("CHAMPIONSHIP STANDINGS:")]
	for i in names.size():
		out.append(tr("%d. %s — %d pts") % [i + 1, names[i], int(table[names[i]])])
	if not names.is_empty() and (str(names[0]).begins_with("1P") or str(names[0]).begins_with("2P")):
		SaveManager.unlock_achievement("champion")
		SaveManager.add_currency(500)
		out.append(tr("Champion bonus: +500 CR"))
	if humans.size() == 2:
		out.append_array(_cup_duel(table))
	Game.championship = {}
	return out


## The final duel of a two-player cup: total cup points of 1P against 2P.
func _cup_duel(table: Dictionary) -> Array:
	var pts := [0, 0]
	for key in table.keys():
		for k in 2:
			if str(key).begins_with("%dP" % (k + 1)):
				pts[k] = int(table[key])
	var races: Array = Game.championship.get("duel", [0, 0])
	var winner := -1
	if pts[0] != pts[1]:
		winner = 0 if pts[0] > pts[1] else 1
	elif int(races[0]) != int(races[1]):
		winner = 0 if int(races[0]) > int(races[1]) else 1
	SaveManager.record_cup_duel(winner)
	var out: Array = [tr("CUP DUEL: 1P %d pts — 2P %d pts · races won %d : %d") % [pts[0], pts[1], int(races[0]), int(races[1])]]
	if winner < 0:
		out.append(tr("THE DUEL IS A DRAW!"))
	else:
		out.append(tr("%dP WINS THE CUP DUEL! (+300 CR)") % (winner + 1))
		SaveManager.add_currency(300)
	return out
