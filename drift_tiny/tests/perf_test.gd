extends Node
## Measures frame cost in races: script time per frame (process + physics),
## draw calls and FPS. Run with a display (xvfb-run on Linux):
##   godot --path . res://tests/perf_test.tscn

const CASES := [
	{"players": 1, "mode": "time_attack", "track": "mountain", "view": "split"},
	{"players": 1, "mode": "time_attack", "track": "neon", "view": "split"},
	{"players": 2, "mode": "versus", "track": "snow", "view": "split"},
	{"players": 2, "mode": "coop", "track": "forest", "view": "shared"},
]


func _ready() -> void:
	get_parent().remove_child.call_deferred(self)
	get_tree().root.add_child.call_deferred(self)
	_run.call_deferred()


func _run() -> void:
	for cfg in CASES:
		await _measure(cfg)
	get_tree().quit()


func _measure(cfg: Dictionary) -> void:
	Game.players = cfg["players"]
	Game.mode = cfg["mode"]
	Game.laps = 3
	Game.view_mode = cfg["view"]
	Game.track_id = cfg["track"]
	Game.goto("race")
	for i in 10:
		await get_tree().process_frame
	var race := get_tree().current_scene as RaceManager
	for h in race.humans:
		(h as Car).controller = AutopilotController.new(1.0, 0.0, 9)
		((h as Car).controller as AutopilotController).drift_happy = 1.0
	for i in 120:   # countdown + get going, skids accumulate
		await get_tree().process_frame
	var proc := 0.0
	var phys := 0.0
	var draws := 0.0
	var n := 0
	var t0 := Time.get_ticks_usec()
	for i in 60:
		await get_tree().process_frame
		proc += Performance.get_monitor(Performance.TIME_PROCESS)
		phys += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
		draws += Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		n += 1
	var fps := n / ((Time.get_ticks_usec() - t0) / 1e6)
	print("PERF %s %dP %s: fps=%.0f process=%.2fms physics=%.2fms draw_calls=%.0f" % [
		cfg["track"], cfg["players"], cfg["view"], fps, proc / n * 1000.0, phys / n * 1000.0, draws / n])
