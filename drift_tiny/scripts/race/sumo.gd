class_name Sumo
extends RefCounted
## Sumo on a round platform above the void: no walls, push the others off.
## A car whose centre leaves the platform falls. The car that last hit it
## gets the push points; the last car standing wins the round. 3 rounds.

const ROUNDS := 3
const PUSH_POINTS := 600
const WIN_POINTS := 2000
const ROUND_LIMIT := 30.0       # then the ring shrinks fast

var race: RaceManager
var cars: Array = []
var alive: Array = []
var round_no := 1
var wins: Dictionary = {}
var ring := 330.0
var _last_hit: Dictionary = {}   # car -> [other, time]
var _pause := 0.0
var _round_t := 0.0
var _falling: Dictionary = {}    # car -> seconds since it went over


func setup(the_race: RaceManager, all: Array) -> void:
	race = the_race
	cars = all
	for c in cars:
		wins[c] = 0
		(c as Car).bumped.connect(_on_bump.bind(c))
	_start_round()


func _on_bump(other: Car, impact: float, me: Car) -> void:
	if impact > 30.0:
		_last_hit[me] = [other, race.race_time]
		_last_hit[other] = [me, race.race_time]


func _start_round() -> void:
	ring = race.track_data.ring_r
	_round_t = 0.0
	alive = cars.duplicate()
	_falling.clear()
	_last_hit.clear()
	var c := race.track_data.arena_rect.get_center()
	for k in cars.size():
		var car := cars[k] as Car
		race.revive(car)
		car.scale = Vector2.ONE
		var a := TAU * k / cars.size()
		var pos := c + Vector2.from_angle(a) * (ring * 0.55)
		car.place(pos, (c - pos).angle())
		car.velocity = Vector2.ZERO


func center() -> Vector2:
	return race.track_data.arena_rect.get_center()


func tick(dt: float) -> void:
	if _pause > 0.0:
		_pause -= dt
		if _pause <= 0.0:
			round_no += 1
			_start_round()
			race.views.message_all(Lang.t("ROUND %d") % round_no, Color("ff5fb8"), 1.4)
		return
	_round_t += dt
	# A long round: the platform crumbles from the edge.
	if _round_t > ROUND_LIMIT:
		ring = maxf(ring - dt * 30.0, 70.0)
	var c := center()
	for f in _falling.keys():
		_falling[f] = float(_falling[f]) + dt
		var car := f as Car
		var k := clampf(1.0 - float(_falling[f]) / 0.5, 0.05, 1.0)
		car.scale = Vector2(k, k)
		if float(_falling[f]) > 0.5:
			car.visible = false
	for a in alive.duplicate():
		var car := a as Car
		if car.global_position.distance_to(c) > ring + 2.0:
			_fall(car)
	_steer_bots()
	if alive.size() <= 1 and _pause <= 0.0:
		if alive.size() == 1:
			var w := alive[0] as Car
			wins[w] = int(wins[w]) + 1
			w.scoring.total += WIN_POINTS
			w.scoring.popup.emit(Lang.t("ROUND WON!"), WIN_POINTS, "zone")
			race.views.message_all(Lang.t("%s WINS THE ROUND!") % race.short_name(w), Color("ffd84a"), 2.0)
		_pause = 2.5 if round_no < ROUNDS else 0.0
		if round_no >= ROUNDS:
			round_no = ROUNDS + 1


func _fall(car: Car) -> void:
	alive.erase(car)
	_falling[car] = 0.0
	var hit: Array = _last_hit.get(car, [])
	if not hit.is_empty() and race.race_time - float(hit[1]) < 3.0 and hit[0] != car:
		var pusher := hit[0] as Car
		pusher.scoring.total += PUSH_POINTS
		pusher.scoring.popup.emit(Lang.t("PUSHED OFF!"), PUSH_POINTS, "bank")
	race.knock_out(car, false)
	car.visible = true
	AudioManager.play("drift_fail", 0.7, -2.0)
	race.views.message_all(Lang.t("%s FALLS!") % race.short_name(car), Color("ff5a5a"), 1.2)


## Bots go for the nearest rival, but never towards the edge: near it they
## turn back to the middle and slow down.
func _steer_bots() -> void:
	var c := center()
	for a in alive:
		var car := a as Car
		var drv := car.controller as FieldDriver
		if drv == null:
			continue
		var best: Car = null
		var best_d := INF
		for o in alive:
			if o == car:
				continue
			var d := car.global_position.distance_to((o as Car).global_position)
			if d < best_d:
				best_d = d
				best = o
		var from_c := car.global_position.distance_to(c)
		if from_c > ring * 0.72 or best == null:
			drv.aim = c
			drv.want_speed = 120.0
		else:
			# Hit them from the side of the centre, so they go outwards.
			var bp := best.global_position + best.velocity * 0.25
			var out_dir := (bp - c).normalized()
			drv.aim = bp + out_dir * 20.0
			drv.want_speed = 9999.0


func is_done() -> bool:
	return round_no > ROUNDS


func mode_line(car: Car) -> String:
	var edge := int(ring - car.global_position.distance_to(center()))
	if car.out:
		return Lang.t("FELL OFF — ROUND %d/%d") % [mini(round_no, ROUNDS), ROUNDS]
	return Lang.t("ROUND %d/%d   ON THE RING %d   EDGE %d") % [mini(round_no, ROUNDS), ROUNDS, alive.size(), maxi(edge, 0)]


## Rounds won first, then points.
func ranked() -> Array:
	var order := cars.duplicate()
	order.sort_custom(func(a, b):
		if int(wins[a]) != int(wins[b]):
			return int(wins[a]) > int(wins[b])
		return (a as Car).scoring.total > (b as Car).scoring.total)
	return order


func title() -> String:
	return Lang.t("%s IS THE SUMO CHAMPION!") % race.short_name(ranked()[0])


func cell(c: Car) -> String:
	return Lang.t("%d rounds won") % int(wins.get(c, 0))


func draw_world(ci: CanvasItem) -> void:
	var c := center()
	if ring < race.track_data.ring_r - 1.0:
		# Crumbled part: the void shows through.
		ci.draw_arc(c, (race.track_data.ring_r + ring) * 0.5, 0, TAU, 64, Color("0b0a16"), race.track_data.ring_r - ring + 2.0)
		ci.draw_arc(c, ring, 0, TAU, 64, Color("ff5fb8"), 2.0)
