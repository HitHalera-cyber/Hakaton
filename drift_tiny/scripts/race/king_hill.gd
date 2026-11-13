class_name KingHill
extends RefCounted
## King of the hill in the city: a glowing zone sits on a street. Points
## flow to whoever is inside it, fast when alone and slowly when it is
## contested, so push the others out. Every 25 s the zone moves on.

const TIME := 150.0
const MOVE_EVERY := 25.0
const RADIUS := 70.0
const SOLO_RATE := 150.0
const SHARED_RATE := 40.0

var race: RaceManager
var cars: Array = []
var zone := Vector2.ZERO
var held: Dictionary = {}        # car -> seconds inside the zone
var _move_t := MOVE_EVERY
var _acc: Dictionary = {}        # car -> points not yet shown
var _rng := RandomNumberGenerator.new()


func setup(the_race: RaceManager, all: Array) -> void:
	race = the_race
	cars = all
	_rng.randomize()
	for c in cars:
		held[c] = 0.0
		_acc[c] = 0.0
	zone = race.track_data.nodes[race.track_data.node_index(3, 2)].lerp(race.track_data.nodes[race.track_data.node_index(4, 2)], 0.5)
	_steer_bots()


func _move_zone() -> void:
	var d := race.track_data
	for _try in 30:
		var n := _rng.randi_range(0, d.nodes.size() - 1)
		var nb: Array = d.links[n]
		var p := d.nodes[n].lerp(d.nodes[int(nb[_rng.randi_range(0, nb.size() - 1)])], 0.5)
		if p.distance_to(zone) > 600.0:
			zone = p
			break
	race.views.message_all(Lang.t("THE HILL MOVES!"), Color("ffd84a"), 1.5)
	AudioManager.play("count", 1.2, -4.0)
	_steer_bots()


func _update_drivers() -> void:
	_steer_bots()


func _steer_bots() -> void:
	for c in cars:
		var drv := (c as Car).controller as CityDriver
		if drv:
			drv.mode = "goto"
			drv.goal_pos = zone + Vector2(_rng.randf_range(-20, 20), _rng.randf_range(-20, 20))


func inside() -> Array:
	return cars.filter(func(c): return (c as Car).global_position.distance_to(zone) < RADIUS)


func tick(dt: float) -> void:
	_move_t -= dt
	if _move_t <= 0.0:
		_move_t = MOVE_EVERY
		_move_zone()
	var ins := inside()
	var rate := SOLO_RATE if ins.size() == 1 else SHARED_RATE
	for c in ins:
		var car := c as Car
		held[car] = float(held[car]) + dt
		_acc[car] = float(_acc[car]) + rate * dt
		if float(_acc[car]) >= 100.0:
			car.scoring.total += 100
			_acc[car] = float(_acc[car]) - 100.0
			car.add_float("+100", Color("ffd84a"))
	# Bots inside keep circling (drifting) on the spot.
	for c in cars:
		var drv := (c as Car).controller as CityDriver
		if drv and (c as Car).global_position.distance_to(zone) < RADIUS * 0.6:
			drv.goal_pos = zone + Vector2.from_angle(race.race_time * 2.0 + float((c as Car).get_instance_id() % 7)) * 40.0


func is_done() -> bool:
	return race.race_time >= TIME


func mode_line(car: Car) -> String:
	var t := RaceHUD.format_time(maxf(TIME - race.race_time, 0.0)).substr(0, 5)
	var ins := inside()
	var state := Lang.t("OUTSIDE %d m") % int(car.global_position.distance_to(zone) / 10.0)
	if car in ins:
		state = Lang.t("KING OF THE HILL!") if ins.size() == 1 else Lang.t("CONTESTED!")
	return Lang.t("%s   MOVES IN %d   %s") % [state, ceili(_move_t), t]


func title() -> String:
	var best: Car = null
	for c in cars:
		if best == null or (c as Car).scoring.total > best.scoring.total:
			best = c
	return Lang.t("%s RULES THE HILL!") % race.short_name(best)


func cell(c: Car) -> String:
	return Lang.t("held %d s") % int(held.get(c, 0.0))


func map_marks(_viewer: Car) -> Array:
	return [[zone, Color("ffd84a"), true]]


func draw_world(ci: CanvasItem) -> void:
	var tt := Time.get_ticks_msec() * 0.004
	var ins := inside()
	var col := Color("ffd84a")
	if ins.size() == 1:
		col = (ins[0] as Car).tag_color if (ins[0] as Car).player_index > 0 else Color("e0e0e8")
	elif ins.size() > 1:
		col = Color("ff5a5a")
	ci.draw_circle(zone, RADIUS, Color(col, 0.12))
	ci.draw_arc(zone, RADIUS, 0, TAU, 48, Color(col, 0.85), 3.0)
	ci.draw_arc(zone, RADIUS - 8.0 + sin(tt * 2.0) * 3.0, 0, TAU, 48, Color(col, 0.35), 2.0)
	# A crown in the middle.
	var c := zone + Vector2(0, sin(tt) * 2.0)
	ci.draw_colored_polygon(PackedVector2Array([c + Vector2(-8, 4), c + Vector2(-8, -4), c + Vector2(-4, 0), c + Vector2(0, -6),
			c + Vector2(4, 0), c + Vector2(8, -4), c + Vector2(8, 4)]), Color("ffd84a"))
	for car in cars:
		if (car as Car).player_index > 0:
			Delivery._arrow(ci, car, zone, (car as Car).tag_color)
