extends Node
## Headless smoke test: opens every menu, then plays one race per config with
## the CPU driving the "human" cars, and reports how each race ended.
## Run:  godot --headless --path . --fixed-fps 60 res://tests/smoke_test.tscn

const CONFIGS := [
	{"players": 1, "mode": "time_attack", "track": "mountain"},
	{"players": 1, "mode": "drift_attack", "track": "neon"},
	{"players": 1, "mode": "ghost", "track": "forest"},
	{"players": 1, "mode": "championship", "track": "mountain"},
	{"players": 1, "mode": "practice", "track": "snow"},
	{"players": 2, "mode": "versus", "track": "snow", "view": "split"},
	{"players": 2, "mode": "coop", "track": "mountain", "view": "shared"},
	{"players": 2, "mode": "time_attack", "track": "forest", "view": "split"},
]
const RACE_TIMEOUT := 90.0

var _failures := 0


func _ready() -> void:
	get_parent().remove_child.call_deferred(self)
	get_tree().root.add_child.call_deferred(self)
	_run.call_deferred()


func _frames(n: int) -> void:
	for i in n:
		await get_tree().physics_frame


func _run() -> void:
	await _frames(2)
	for key in ["menu", "setup", "garage", "records", "settings"]:
		Game.goto(key)
		await _frames(30)
		print("SCENE ok: ", key, " -> ", get_tree().current_scene.name)
	for cfg in CONFIGS:
		await _race(cfg)
	print("SMOKE DONE, failures: ", _failures)
	get_tree().quit(1 if _failures > 0 else 0)


func _race(cfg: Dictionary) -> void:
	Game.players = cfg["players"]
	Game.mode = cfg["mode"]
	Game.laps = 1
	Game.view_mode = cfg.get("view", "split")
	if Game.mode == "championship":
		Game.start_championship()
	else:
		Game.track_id = cfg["track"]
	Game.goto("race")
	await _frames(3)
	var race := get_tree().current_scene as RaceManager
	if race == null:
		_failures += 1
		print("FAIL no race scene for ", cfg)
		return
	for h in race.humans:
		(h as Car).controller = AutopilotController.new(0.95, 0.0, 5)
	var t := 0.0
	var limit := 45.0 if Game.mode == "practice" else RACE_TIMEOUT
	while t < limit and race.state != "results":
		await get_tree().physics_frame
		t += 1.0 / 60.0
	var line := "%s %dP %s: state=%s t=%.1fs" % [Game.mode, Game.players, race.track_data.id, race.state, t]
	for c in race.cars:
		var info: Dictionary = race.racers[c]
		line += " | %s laps=%d best=%.1f score=%d combo=%d" % [info["name"], int(info["laps_done"]),
				float(info["best_lap"]), (c as Car).scoring.total, (c as Car).scoring.best_combo]
	var ok := race.state == "results" or (Game.mode == "practice" and int(race.racers[race.humans[0]]["laps_done"]) >= 1)
	if not ok:
		_failures += 1
	print(("RACE ok: " if ok else "RACE FAIL: ") + line)
