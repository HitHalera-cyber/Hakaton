class_name GateRush
extends RefCounted
## Gate rush on the stadium: a slalom of cone gates. Drive through them in
## order; each gate adds time to your clock, a gate taken sideways (in a
## drift) adds more time and points. When your clock hits zero you are out.
## The run with the most points wins.

const START_TIME := 14.0
const GATE_TIME := 3.0
const DRIFT_TIME := 1.2
const GATE_POINTS := 200
const DRIFT_POINTS := 400
const HALF_W := 24.0

var race: RaceManager
var cars: Array = []
var gates: Array = []            # {a: Vector2, b: Vector2, c: Vector2}
var next: Dictionary = {}        # car -> gate index
var clock: Dictionary = {}       # car -> seconds left
var passed: Dictionary = {}      # car -> gates passed
var _prev: Dictionary = {}       # car -> previous position


func setup(the_race: RaceManager, all: Array) -> void:
	race = the_race
	cars = all
	var r := race.track_data.arena_rect
	var c := r.get_center()
	# A wavy loop round the pitch: every other gate is pulled in or pushed
	# out, so the line snakes (a slalom), and the gates face along the loop.
	var n := 14
	var pts: Array = []
	for k in n:
		var a := TAU * k / n - PI * 0.5
		var wob := 1.0 + (0.14 if k % 2 == 0 else -0.14)
		pts.append(c + Vector2(cos(a) * 390.0 * wob, sin(a) * 215.0 * wob))
	for k in n:
		var p: Vector2 = pts[k]
		var dir := ((pts[(k + 1) % n] as Vector2) - (pts[(k - 1 + n) % n] as Vector2)).normalized()
		var side := Vector2(-dir.y, dir.x)
		gates.append({"a": p - side * HALF_W, "b": p + side * HALF_W, "c": p, "dir": dir})
	for k in cars.size():
		var car := cars[k] as Car
		next[car] = 0
		clock[car] = START_TIME
		passed[car] = 0
		# Line up before the first gate, side by side.
		var g: Dictionary = gates[0]
		var back: Vector2 = (g["c"] as Vector2) - (g["dir"] as Vector2) * (70.0 + (k / 3) * 30.0)
		var off := Vector2(-(g["dir"] as Vector2).y, (g["dir"] as Vector2).x) * ((k % 3) - 1) * 22.0
		car.place(back + off, (g["dir"] as Vector2).angle())
		_prev[car] = car.global_position


func tick(dt: float) -> void:
	for c in cars:
		var car := c as Car
		if car.out:
			continue
		clock[car] = float(clock[car]) - dt
		var g: Dictionary = gates[int(next[car])]
		var p0: Vector2 = _prev[car]
		var p1 := car.global_position
		_prev[car] = p1
		if Geometry2D.segment_intersects_segment(p0, p1, g["a"], g["b"]) != null:
			var sideways := car.drifting and car.slip_deg > 18.0
			# Each gate gives a little less time: the run gets tighter.
			var gain := maxf(GATE_TIME - int(passed[car]) * 0.06, 1.1)
			clock[car] = float(clock[car]) + gain + (DRIFT_TIME if sideways else 0.0)
			passed[car] = int(passed[car]) + 1
			next[car] = (int(next[car]) + 1) % gates.size()
			var pts := GATE_POINTS + (DRIFT_POINTS if sideways else 0)
			car.scoring.total += pts
			car.add_float("DRIFT GATE!" if sideways else "GATE", Color("ffd84a") if sideways else Color("7dff8a"))
			if car.player_index > 0:
				AudioManager.play("lap" if sideways else "count", 1.3, -6.0)
		var drv := car.controller as FieldDriver
		if drv:
			# Aim a bit past the gate centre so the line goes through it.
			var ng: Dictionary = gates[int(next[car])]
			drv.aim = (ng["c"] as Vector2) + (ng["dir"] as Vector2) * 20.0
			drv.want_speed = 9999.0
		if float(clock[car]) <= 0.0:
			clock[car] = 0.0
			race.knock_out(car, false)
			race.views.message_for(car, Lang.t("TIME UP!"), Color("ff5a5a"), 2.0)


func is_done() -> bool:
	for c in race.humans:
		if not (c as Car).out:
			return false
	return true


func mode_line(car: Car) -> String:
	if car.out:
		return Lang.t("TIME UP — %d GATES") % int(passed[car])
	return Lang.t("TIME %.1f   GATES %d   NEXT %d") % [float(clock[car]), int(passed[car]), int(next[car]) + 1]


func title() -> String:
	var best: Car = null
	for c in cars:
		if best == null or (c as Car).scoring.total > best.scoring.total:
			best = c
	return Lang.t("%s TAKES THE GATE RUSH!") % race.short_name(best)


func cell(c: Car) -> String:
	return Lang.t("%d gates") % int(passed.get(c, 0))


func draw_world(ci: CanvasItem) -> void:
	# Who is heading for which gate: the players' colours ring their gate.
	var targets: Dictionary = {}
	for c in race.humans:
		targets[int(next[c])] = (c as Car).tag_color
	for k in gates.size():
		var g: Dictionary = gates[k]
		var a: Vector2 = g["a"]
		var b: Vector2 = g["b"]
		var lit := targets.has(k)
		if lit:
			var col: Color = targets[k]
			ci.draw_line(a, b, Color(col, 0.45), 4.0)
			PixelText.draw_centered(ci, (g["c"] as Vector2) - Vector2(0, 3), str(k + 1), col)
		else:
			ci.draw_line(a, b, Color(1, 1, 1, 0.12), 1.0)
		for p in [a, b]:
			ci.draw_circle((p as Vector2) + Vector2(1, 2), 4.0, Color(0, 0, 0, 0.3))
			ci.draw_circle(p, 4.0, Color("ff7a1a"))
			ci.draw_circle(p, 1.5, Color.WHITE)
	for c in race.humans:
		var car := c as Car
		if not car.out:
			Delivery._arrow(ci, car, gates[int(next[car])]["c"], car.tag_color)
