extends Node
## Renders screenshots of menus and races (needs a display, e.g. xvfb-run).
## Run:  xvfb-run godot --path . res://tests/screenshots.tscn -- <out_dir> [styles]
## With "styles" it renders the same race moment once per graphics style.

var _out := "user://shots"


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		_out = args[0]
	DirAccess.make_dir_recursive_absolute(_out)
	get_parent().remove_child.call_deferred(self)
	get_tree().root.add_child.call_deferred(self)
	_run.call_deferred()


func _wait(sec: float) -> void:
	for i in int(sec * 60.0):
		await get_tree().process_frame


func _shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(_out.path_join(name + ".png"))
	print("shot ", name)


func _race(players: int, mode: String, track: String, view: String, sec: float, name: String) -> void:
	Game.players = players
	Game.mode = mode
	Game.laps = 3
	Game.view_mode = view
	Game.track_id = track
	Game.goto("race")
	await _wait(0.1)
	var race := get_tree().current_scene as RaceManager
	for h in race.humans:
		(h as Car).controller = AutopilotController.new(1.0, 0.0, 9)
		((h as Car).controller as AutopilotController).drift_happy = 1.0
	await _wait(sec)
	await _shot(name)


func _run() -> void:
	if "ru" in OS.get_cmdline_user_args():
		SaveManager.data["settings"]["style"] = "neon_sunset"
		Lang.apply("ru")
		Game.goto("menu")
		await _wait(3.0)
		await _shot("ru_menu")
		Game.goto("settings")
		await _wait(0.5)
		await _shot("ru_settings")
		Game.goto("garage")
		await _wait(0.5)
		await _shot("ru_garage")
		await _race(2, "versus", "neon", "split", 12.0, "ru_race")
		get_tree().quit()
		return
	if "worlds" in OS.get_cmdline_user_args():
		SaveManager.data["settings"]["style"] = "neon_sunset"
		for tid in ["desk", "midnight", "vector", "autumn"]:
			await _race(2, "versus", tid, "split", 9.0, "world_%s_split" % tid)
			await _race(1, "time_attack", tid, "split", 12.0, "world_%s" % tid)
		get_tree().quit()
		return
	if "modes" in OS.get_cmdline_user_args():
		await _modes()
		get_tree().quit()
		return
	if "city" in OS.get_cmdline_user_args():
		await _city()
		get_tree().quit()
		return
	if "features" in OS.get_cmdline_user_args():
		await _features()
		get_tree().quit()
		return
	if "drift" in OS.get_cmdline_user_args():
		# A burst of frames from a drifting car, to check the drift effects.
		SaveManager.data["settings"]["style"] = "neon_sunset"
		await _race(1, "drift_attack", "mountain", "split", 6.0, "drift_00")
		for i in 12:
			await _wait(1.2)
			await _shot("drift_%02d" % (i + 1))
		get_tree().quit()
		return
	if "styles" in OS.get_cmdline_user_args():
		var n := 1
		for sid in GraphicsStyle.ORDER:
			SaveManager.data["settings"]["style"] = sid
			await _race(1, "time_attack", "mountain", "split", 14.0, "style_%d_%s" % [n, sid])
			n += 1
		get_tree().quit()
		return
	Game.goto("menu")
	await _wait(6.0)
	await _shot("01_menu")
	Game.goto("setup")
	await _wait(0.5)
	await _shot("02_setup")
	Game.goto("garage")
	await _wait(0.5)
	await _shot("03_garage")
	await _race(1, "time_attack", "mountain", "split", 9.5, "04_mountain_1p")
	await _race(2, "versus", "neon", "split", 11.0, "05_neon_split")
	await _race(2, "coop", "forest", "shared", 12.0, "06_forest_shared")
	await _race(1, "drift_attack", "snow", "split", 13.0, "07_snow_1p")
	get_tree().quit()


## The new features: stars, hazards and crowds, gymkhana, training, night and
## rain, photo mode, the slow-motion replay, the duel notes and table.
func _features() -> void:
	SaveManager.data["settings"]["style"] = "neon_sunset"
	Lang.apply("ru")
	SaveManager.data["stars"]["mountain"] = [true, true, false]
	Game.players = 1
	Game.mode = "time_attack"
	Game.track_id = "mountain"
	Game.goto("setup")
	await _wait(0.6)
	await _shot("f_setup_stars")
	await _race(1, "drift_attack", "mountain", "split", 7.0, "f_race_a")
	await _wait(5.0)
	await _shot("f_race_b")
	await _wait(5.0)
	await _shot("f_race_c")
	# Night and rain, forced.
	var race := get_tree().current_scene as RaceManager
	race.day_cycle.phase = 0.7
	race.day_cycle._set_rain(true)
	await _wait(3.0)
	await _shot("f_night_rain")
	# Photo mode.
	race.photo.open()
	for i in 30:
		race.photo._zoom_by(0.03)
		await get_tree().process_frame
	await _wait(0.3)
	await _shot("f_photo")
	var path: String = await race.photo.capture()
	print("photo saved ", path, " exists=", FileAccess.file_exists(path))
	await _wait(0.3)
	await _shot("f_photo_saved")
	race.photo.close()
	await _race(1, "gymkhana", "arena", "split", 14.0, "f_gymkhana")
	await _race(1, "training", "arena", "split", 4.0, "f_training")
	# A 2P race to the end: slow-motion replay, then results with the duel.
	Game.laps = 1
	await _race(2, "versus", "snow", "split", 0.5, "f_versus_start")
	race = get_tree().current_scene as RaceManager
	race.laps_total = 1
	var shot_replay := false
	for i in 60 * 120:
		await get_tree().process_frame
		if race.state == "replay" and not shot_replay:
			await _wait(1.0)
			await _shot("f_replay")
			var p0 := race._replay_car.global_position
			print("replay rf=", race._rf, " end=", race._rf_end, " win=", race._replay_car.scoring.best_window, " t=", race.race_time)
			await _wait(2.0)
			print("replay rf=", race._rf, " state=", race.state)
			print("replay moved ", p0.distance_to(race._replay_car.global_position), " px in 2 s real time")
			shot_replay = true
		if race.state == "results":
			break
	await _wait(1.0)
	await _shot("f_results_duel")
	Game.goto("records")
	await _wait(0.5)
	for n in get_tree().current_scene.get_children():
		if n is ScrollContainer:
			(n as ScrollContainer).scroll_vertical = 100000
	await _wait(0.3)
	await _shot("f_records")


func _city() -> void:
	SaveManager.data["settings"]["style"] = "neon_sunset"
	Lang.apply("ru")
	Game.players = 1
	Game.mode = "police"
	Game.roles = ["robber", "cop"]
	Game.cops = 4
	Game.goto("setup")
	await _wait(0.6)
	await _shot("c_setup")
	Game.mode = "elimination"
	Game.goto("setup")
	await _wait(0.6)
	await _shot("c_setup_elim")
	Game.goto("garage")
	await _wait(0.6)
	await _shot("c_garage")
	Game.mode = "police"
	Game.goto("race")
	await _wait(0.1)
	var race := get_tree().current_scene as RaceManager
	for h in race.humans:
		(h as Car).controller = CityDriver.new(race.track_data, 9, 0.95)
	race.game.call("_update_drivers")
	for i in 5:
		await _wait(3.0)
		await _shot("c_police_%d" % i)
		print("t=", race.race_time, " state=", race.state, " bust=", (race.game as PoliceChase).bust.values())
	race.photo.open()
	race.photo._cam.zoom = Vector2(0.6, 0.6)
	await _wait(0.3)
	await _shot("c_overview")
	race.photo.close()
	Game.mode = "bomb"
	Game.bots = 4
	Game.goto("race")
	await _wait(0.1)
	race = get_tree().current_scene as RaceManager
	for h in race.humans:
		(h as Car).controller = CityDriver.new(race.track_data, 9, 0.95)
	await _wait(9.0)
	await _shot("c_bomb")
	Game.players = 2
	Game.mode = "police"
	Game.roles = ["robber", "cop"]
	Game.goto("race")
	await _wait(8.0)
	await _shot("c_police_2p")


## One shot of each party mode in play, plus the setup screen of two.
func _modes() -> void:
	SaveManager.data["settings"]["style"] = "neon_sunset"
	Lang.apply("ru")
	Game.players = 1
	Game.bots = 3
	for m in ["soccer", "sumo"]:
		Game.mode = m
		Game.goto("setup")
		await _wait(0.6)
		await _shot("m_setup_" + m)
	for m in ["delivery", "koth", "soccer", "sumo", "gates"]:
		Game.mode = m
		Game.goto("race")
		await _wait(0.1)
		var race := get_tree().current_scene as RaceManager
		for h in race.humans:
			if race.track_data.city:
				(h as Car).controller = CityDriver.new(race.track_data, 9, 0.95)
			else:
				(h as Car).controller = FieldDriver.new(0.95)
		if race.game.has_method("_update_drivers"):
			race.game.call("_update_drivers")
		await _wait(11.0)
		await _shot("m_" + m)
		if m == "soccer" or m == "sumo":
			race.photo.open()
			race.photo._cam.zoom = Vector2(0.6, 0.6)
			race.photo._cam.global_position = race.track_data.arena_rect.get_center()
			await _wait(0.3)
			await _shot("m_%s_wide" % m)
			race.photo.close()
