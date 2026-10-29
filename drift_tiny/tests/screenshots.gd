extends Node
## Renders screenshots of menus and races (needs a display, e.g. xvfb-run).
## Run:  xvfb-run godot --path . --fixed-fps 60 res://tests/screenshots.tscn -- <out_dir>

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
