class_name HotPotato
extends RefCounted
## Hot potato in the city: one car carries a bomb with a burning fuse and
## passes it on by touching another car. When the fuse runs out the carrier
## is knocked out and a new bomb appears. The last car left wins.

const FUSE := 20.0
const PASS_RANGE := 22.0

var race: RaceManager
var alive: Array = []
var carrier: Car
var fuse := FUSE
var winner: Car
var _pass_cd := 0.0
var _next := 2.5
var _rng := RandomNumberGenerator.new()


func setup(the_race: RaceManager, all: Array) -> void:
	race = the_race
	alive = all.duplicate()
	_rng.randomize()
	_update_drivers()


func tick(dt: float) -> void:
	if is_done():
		return
	_pass_cd = maxf(_pass_cd - dt, 0.0)
	if carrier == null:
		_next -= dt
		if _next <= 0.0:
			carrier = alive[_rng.randi_range(0, alive.size() - 1)]
			fuse = FUSE
			_pass_cd = 1.5
			race.views.message_all(Lang.t("%s HAS THE BOMB!") % race.short_name(carrier), Color("ff7a1a"), 1.6)
			AudioManager.play("count", 0.7)
	else:
		fuse -= dt
		if _pass_cd <= 0.0:
			for c in alive:
				var o := c as Car
				if o != carrier and o.global_position.distance_to(carrier.global_position) < PASS_RANGE:
					_give(o)
					break
		if fuse <= 0.0:
			_explode()
	for c in alive:
		var car := c as Car
		if car == carrier:
			car.badge = "BOMB %d" % ceili(fuse)
			car.badge_color = Color("ff7a1a") if int(fuse * 4.0) % 2 == 0 else Color("ffe14a")
		else:
			car.badge = ""
	_update_drivers()
	if alive.size() == 1:
		winner = alive[0]
		winner.badge = ""


func _give(to: Car) -> void:
	carrier.add_float("PASSED!", Color("7dff8a"))
	carrier.scoring.total += 300
	to.add_float("BOMB!", Color("ff7a1a"))
	carrier.badge = ""
	carrier = to
	_pass_cd = 1.0
	AudioManager.play("bump", 1.4, -4.0)


func _explode() -> void:
	var car := carrier
	carrier = null
	car.badge = ""
	alive.erase(car)
	race.knock_out(car, false)
	race.views.message_all(Lang.t("BOOM! %s IS OUT") % race.short_name(car), Color("ff7a1a"), 2.0)
	AudioManager.play("crash", 0.6, 0.0)
	for cam in race.views.cameras:
		(cam as CameraController).shake(8.0)
	for c in alive:
		(c as Car).scoring.total += 1000
	_next = 2.5


func _update_drivers() -> void:
	for c in alive:
		var drv := (c as Car).controller as CityDriver
		if drv == null:
			continue
		if carrier == null:
			drv.mode = "cruise"
		elif c == carrier:
			drv.mode = "chase"
			var best: Car = null
			var best_d := INF
			for o in alive:
				if o == c:
					continue
				var d := (c as Car).global_position.distance_to((o as Car).global_position)
				if d < best_d:
					best_d = d
					best = o
			drv.target = best
		else:
			drv.mode = "flee"
			drv.threats = [carrier]
			drv.goodies = []


func is_done() -> bool:
	return winner != null or alive.size() <= 1


func mode_line(car: Car) -> String:
	if car.out:
		return Lang.t("OUT — WAIT FOR THE OTHERS")
	if carrier == null:
		return Lang.t("NEW BOMB SOON   ALIVE %d") % alive.size()
	if car == carrier:
		return Lang.t("YOU HAVE THE BOMB! %d s — TOUCH SOMEONE") % ceili(fuse)
	return Lang.t("RUN! BOMB: %s %d s   ALIVE %d") % [race.short_name(carrier), ceili(fuse), alive.size()]


func title() -> String:
	if winner:
		return Lang.t("%s SURVIVES!") % race.short_name(winner)
	return Lang.t("RESULTS")
