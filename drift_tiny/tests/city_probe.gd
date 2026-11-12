extends Node
## Police chase probe: prints the robber bot's speed, bust meter and nearest
## cop every second (headless). Run: godot --headless --path . --fixed-fps 60 res://tests/city_probe.tscn


func _ready() -> void:
	get_parent().remove_child.call_deferred(self)
	get_tree().root.add_child.call_deferred(self)
	_run.call_deferred()


func _run() -> void:
	Game.players = 1
	Game.mode = "police"
	Game.roles = ["cop", "cop"]
	Game.cops = int(OS.get_environment("COPS")) if OS.get_environment("COPS") != "" else 3
	Game.goto("race")
	for i in 3:
		await get_tree().physics_frame
	var race := get_tree().current_scene as RaceManager
	for h in race.humans:
		(h as Car).controller = CityDriver.new(race.track_data, 9, 0.88)
	race.game.call("_update_drivers")
	var pc := race.game as PoliceChase
	var rb: Car = pc.robbers[0]
	var t := 0
	while race.state == "countdown" or race.state == "racing":
		for k in 60:
			await get_tree().physics_frame
		t += 1
		var near := INF
		for c in pc.cops:
			near = minf(near, rb.global_position.distance_to((c as Car).global_position))
		var drv := rb.controller as CityDriver
		print("t=%d spd=%d bust=%.2f near=%d pos=%s path=%s rev=%.1f" % [t, rb.speed, float(pc.bust[rb]), near, rb.global_position.round(), str(drv._path), drv._rev_t])
		if t > 160:
			break
	print("END ", race.state, " ", pc.title())
	get_tree().quit()
