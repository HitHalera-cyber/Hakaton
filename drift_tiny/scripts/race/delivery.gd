class_name Delivery
extends RefCounted
## Courier rush in the city: every car has its own job. Pick the parcel up,
## drop it at the address before its timer runs out. Fast drops pay more,
## drifting on the way still scores. Most points after 3:00 wins.

const TIME := 180.0
const REACH := 24.0
const PAY := 1000

var race: RaceManager
var jobs: Dictionary = {}       # car -> {stage, pos, t, from}
var done_jobs: Dictionary = {}  # car -> deliveries made
var _rng := RandomNumberGenerator.new()


func setup(the_race: RaceManager, all: Array) -> void:
	race = the_race
	_rng.randomize()
	for c in all:
		done_jobs[c] = 0
		_new_job(c)


func _spot(away_from: Vector2, min_d: float) -> Vector2:
	var d := race.track_data
	for _try in 40:
		var n := _rng.randi_range(0, d.nodes.size() - 1)
		var nb: Array = d.links[n]
		var m: int = nb[_rng.randi_range(0, nb.size() - 1)]
		var p := d.nodes[n].lerp(d.nodes[m], _rng.randf_range(0.3, 0.7))
		if p.distance_to(away_from) >= min_d:
			return p
	return d.nodes[0]


func _leg_time(a: Vector2, b: Vector2) -> float:
	# Street distance is longer than the straight line: allow for it.
	return a.distance_to(b) * 1.35 / 150.0 + 7.0


func _new_job(c: Car) -> void:
	var p := _spot(c.global_position, 350.0)
	jobs[c] = {"stage": "pickup", "pos": p, "t": _leg_time(c.global_position, p)}
	_steer_bot(c)


## Re-sends every bot to its current target (after a controller swap).
func _update_drivers() -> void:
	for c in jobs.keys():
		_steer_bot(c)


func _steer_bot(c: Car) -> void:
	var drv := c.controller as CityDriver
	if drv:
		drv.mode = "goto"
		drv.goal_pos = jobs[c]["pos"]


func tick(dt: float) -> void:
	for c in jobs.keys():
		var car := c as Car
		var job: Dictionary = jobs[car]
		job["t"] = float(job["t"]) - dt
		if car.global_position.distance_to(job["pos"]) < REACH:
			if job["stage"] == "pickup":
				var drop := _spot(car.global_position, 900.0)
				job["stage"] = "drop"
				job["from"] = job["pos"]
				job["pos"] = drop
				job["t"] = _leg_time(car.global_position, drop)
				car.add_float("PARCEL!", Color("ffd84a"))
				if car.player_index > 0:
					AudioManager.play("count", 1.4, -6.0)
				_steer_bot(car)
			else:
				var pts := PAY + int(float(job["t"]) * 40.0)
				car.scoring.total += pts
				car.scoring.popup.emit(Lang.t("DELIVERED!"), pts, "zone")
				done_jobs[car] = int(done_jobs[car]) + 1
				if car.player_index > 0:
					AudioManager.play("reward", 1.2, -4.0)
				_new_job(car)
		elif float(job["t"]) <= 0.0:
			car.scoring.popup.emit(Lang.t("TOO LATE"), 0, "fail")
			_new_job(car)


func is_done() -> bool:
	return race.race_time >= TIME


func mode_line(car: Car) -> String:
	var job: Dictionary = jobs.get(car, {})
	if job.is_empty():
		return ""
	var left := RaceHUD.format_time(maxf(TIME - race.race_time, 0.0)).substr(0, 5)
	var dist := int(car.global_position.distance_to(job["pos"]) / 10.0)
	var what := Lang.t("PICK UP") if job["stage"] == "pickup" else Lang.t("DELIVER")
	return Lang.t("%s %d m  %d s   DONE %d   %s") % [what, dist, ceili(float(job["t"])), int(done_jobs[car]), left]


func title() -> String:
	var best: Car = null
	for c in jobs.keys():
		if best == null or (c as Car).scoring.total > best.scoring.total:
			best = c
	return Lang.t("%s IS THE COURIER OF THE DAY!") % race.short_name(best)


func cell(c: Car) -> String:
	return Lang.t("%d parcels") % int(done_jobs.get(c, 0))


## Minimap marks for one viewer: their own target big, others small.
func map_marks(viewer: Car) -> Array:
	var out: Array = []
	for c in jobs.keys():
		var job: Dictionary = jobs[c]
		var col := Color("ffd84a") if job["stage"] == "pickup" else Color("ff7a1a")
		out.append([job["pos"], col if c == viewer else Color(col, 0.35), c == viewer])
	return out


func draw_world(ci: CanvasItem) -> void:
	var tt := Time.get_ticks_msec() * 0.005
	for c in jobs.keys():
		var car := c as Car
		var job: Dictionary = jobs[car]
		var p: Vector2 = job["pos"]
		var mine := car.player_index > 0
		var col := car.tag_color if mine else Color(0.8, 0.8, 0.85, 0.6)
		if job["stage"] == "pickup":
			# A parcel box.
			var bob := sin(tt + p.x) * 1.5
			ci.draw_rect(Rect2(p + Vector2(-5, -5 + bob) + Vector2(1, 2), Vector2(10, 10)), Color(0, 0, 0, 0.35))
			ci.draw_rect(Rect2(p + Vector2(-5, -5 + bob), Vector2(10, 10)), Color("c8925a"))
			ci.draw_rect(Rect2(p + Vector2(-1, -5 + bob), Vector2(2, 10)), Color("8a5a30"))
			ci.draw_arc(p, 14.0 + sin(tt * 2.0) * 1.5, 0, TAU, 24, col, 1.5)
		else:
			# The address: a pulsing target.
			for k in 3:
				ci.draw_arc(p, 6.0 + k * 6.0 + fmod(tt * 4.0, 6.0), 0, TAU, 24, Color(col, 0.8 - k * 0.25), 2.0)
			ci.draw_circle(p, 3.0, col)
		if mine:
			_arrow(ci, car, p, col)


## A small arrow next to a player's car pointing at their target.
static func _arrow(ci: CanvasItem, car: Car, target: Vector2, col: Color) -> void:
	var from := car.visual_position()
	if from.distance_to(target) < 60.0:
		return
	var dir := (target - from).normalized()
	var tip := from + dir * 26.0
	var side := Vector2(-dir.y, dir.x)
	ci.draw_colored_polygon(PackedVector2Array([tip, tip - dir * 7.0 + side * 4.0, tip - dir * 7.0 - side * 4.0]), Color(col, 0.9))
