class_name PoliceChase
extends RefCounted
## Police chase in the city. Robbers grab cash bags and try to stay free until
## the time runs out; cops box them in. A robber is busted when a cop stays
## close long enough (much faster if the robber is slow or rammed). The cops
## win when every robber is busted.

const TIME := 150.0
const BUST_RANGE := 46.0
const CASH := 500
const BUST_POINTS := 1500
const ESCAPE_BONUS := 2000

var race: RaceManager
var robbers: Array = []
var cops: Array = []
var bust: Dictionary = {}        # robber -> 0..1
var busts: Dictionary = {}       # cop -> busts made
var cash: Array = []             # Vector2 positions of cash bags
var winner := ""                 # "robbers" / "cops" once over
var _rng := RandomNumberGenerator.new()
var _ram_cd: Dictionary = {}     # robber -> seconds until a ram counts again


func setup(the_race: RaceManager, robber_cars: Array, cop_cars: Array) -> void:
	race = the_race
	robbers = robber_cars
	cops = cop_cars
	_rng.randomize()
	for r in robbers:
		bust[r] = 0.0
		(r as Car).badge = "$"
		(r as Car).badge_color = Color("7dff8a")
		(r as Car).bumped.connect(_on_bump.bind(r))
	for c in cops:
		busts[c] = 0
		(c as Car).siren = true
		(c as Car).bumped.connect(_on_bump.bind(c))
	for k in 7:
		cash.append(_cash_spot())
	_update_drivers()


func _cash_spot() -> Vector2:
	var d := race.track_data
	var n := _rng.randi_range(0, d.nodes.size() - 1)
	var nb: Array = d.links[n]
	var m: int = nb[_rng.randi_range(0, nb.size() - 1)]
	return d.nodes[n].lerp(d.nodes[m], _rng.randf_range(0.3, 0.7))


func free_robbers() -> Array:
	return robbers.filter(func(r): return not (r as Car).out)


## Cops ramming a robber bring the bust closer.
func _on_bump(other: Car, impact: float, me: Car) -> void:
	if impact < 50.0:
		return
	var robber: Car = null
	if me in robbers and other in cops:
		robber = me
	elif me in cops and other in robbers:
		robber = other
	if robber and not robber.out and float(_ram_cd.get(robber, 0.0)) <= 0.0:
		_ram_cd[robber] = 0.6
		bust[robber] = minf(float(bust[robber]) + 0.08, 0.99)


func tick(dt: float) -> void:
	if winner != "":
		return
	for r in _ram_cd.keys():
		_ram_cd[r] = float(_ram_cd[r]) - dt
	for r in free_robbers():
		var car := r as Car
		var near := false
		for c in cops:
			if car.global_position.distance_to((c as Car).global_position) < BUST_RANGE:
				near = true
				break
		var b: float = bust[car]
		# Boxed in and slow: busted in about a second. Fast and only
		# tailed: the meter barely moves.
		if near:
			b += dt * (0.5 if car.speed < 50.0 else 0.1)
		else:
			b = maxf(b - dt * 0.3, 0.0)
		bust[car] = b
		if b >= 1.0:
			_busted(car)
			continue
		for k in cash.size():
			if car.global_position.distance_to(cash[k]) < 20.0:
				car.scoring.total += CASH
				car.scoring.popup.emit(Lang.t("CASH"), CASH, "bank")
				car.add_float("+$", Color("7dff8a"))
				AudioManager.play("reward", 1.3, -6.0)
				cash[k] = _cash_spot()
	_update_drivers()
	if free_robbers().is_empty():
		winner = "cops"
	elif race.race_time >= TIME:
		winner = "robbers"
		for r in free_robbers():
			(r as Car).scoring.total += ESCAPE_BONUS


func _busted(car: Car) -> void:
	var best: Car = null
	var best_d := INF
	for c in cops:
		var d := car.global_position.distance_to((c as Car).global_position)
		if d < best_d:
			best_d = d
			best = c
	if best:
		busts[best] = int(busts[best]) + 1
		best.scoring.total += BUST_POINTS
		best.scoring.popup.emit(Lang.t("BUSTED!"), BUST_POINTS, "zone")
	race.knock_out(car, false)
	car.badge = ""
	race.views.message_all(Lang.t("%s BUSTED!") % race.short_name(car), Color("3a7bff"), 2.0)
	AudioManager.play("crash", 0.7, -2.0)


## Bot cops chase the nearest free robber; bot robbers run from the cops.
func _update_drivers() -> void:
	var free := free_robbers()
	for c in cops:
		var drv := (c as Car).controller as CityDriver
		if drv == null:
			continue
		drv.mode = "chase"
		var best: Car = null
		var best_d := INF
		for r in free:
			var d := (c as Car).global_position.distance_to((r as Car).global_position)
			if d < best_d:
				best_d = d
				best = r
		drv.target = best
		if best == null:
			drv.mode = "cruise"
	for r in robbers:
		var drv := (r as Car).controller as CityDriver
		if drv == null:
			continue
		drv.mode = "flee"
		drv.threats = cops
		drv.goodies = cash


func is_done() -> bool:
	return winner != ""


func time_left() -> float:
	return maxf(TIME - race.race_time, 0.0)


func mode_line(car: Car) -> String:
	var t := RaceHUD.format_time(time_left()).substr(0, 5)
	if car in robbers:
		if car.out:
			return Lang.t("BUSTED — WAIT FOR THE OTHERS")
		return Lang.t("ESCAPE %s   BUST %d%%") % [t, int(float(bust[car]) * 100.0)]
	var nearest := INF
	for r in free_robbers():
		nearest = minf(nearest, car.global_position.distance_to((r as Car).global_position))
	var left := free_robbers().size()
	return Lang.t("CATCH THEM %s   LEFT %d   %d m") % [t, left, int(nearest / 10.0) if nearest < INF else 0]


func title() -> String:
	if winner == "cops":
		return Lang.t("BUSTED! THE COPS WIN")
	return Lang.t("THE ROBBERS GOT AWAY!")


## Cash bags, drawn by the race in the world (bobbing green money bags).
func draw_cash(ci: CanvasItem) -> void:
	var t := Time.get_ticks_msec() * 0.004
	for k in cash.size():
		var p: Vector2 = cash[k] + Vector2(0, sin(t + k) * 1.5)
		ci.draw_circle(cash[k] + Vector2(1, 3), 5.0, Color(0, 0, 0, 0.35))
		ci.draw_circle(p, 5.5, Color("2e7d32"))
		ci.draw_circle(p, 4.5, Color("43a047"))
		ci.draw_rect(Rect2(p - Vector2(1.5, 6.5), Vector2(3, 2)), Color("2e7d32"))
		PixelText.draw_centered(ci, p - Vector2(0, 2), "$", Color("d8ffd0"))
