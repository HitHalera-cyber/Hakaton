class_name Elimination
extends RefCounted
## Elimination on a track: every STEP seconds the last car in the race order
## is knocked out. The last one standing wins.

const STEP := 20.0

var race: RaceManager
var alive: Array = []
var timer := STEP
var winner: Car


func setup(the_race: RaceManager, all: Array) -> void:
	race = the_race
	alive = all.duplicate()


func tick(dt: float) -> void:
	if is_done():
		return
	timer -= dt
	if timer > 0.0:
		return
	timer = STEP
	var last: Car = null
	var worst := -1
	for c in alive:
		var pos := int(race.racers[c]["position"])
		if pos > worst:
			worst = pos
			last = c
	alive.erase(last)
	race.knock_out(last, true)
	race.views.message_all(Lang.t("%s IS OUT!") % race.short_name(last), Color("ff5a5a"), 2.0)
	AudioManager.play("crash", 0.8, -4.0)
	if alive.size() == 1:
		winner = alive[0]


func humans_left() -> bool:
	for c in alive:
		if (c as Car).player_index > 0:
			return true
	return false


func is_done() -> bool:
	return alive.size() <= 1 or not humans_left()


func mode_line(car: Car) -> String:
	if car.out:
		return Lang.t("OUT — WAIT FOR THE OTHERS")
	var p := int(race.racers[car]["position"])
	var danger := p == _last_position()
	var line := Lang.t("NEXT OUT IN %d s   ALIVE %d") % [ceili(timer), alive.size()]
	return line + ("   " + Lang.t("YOU ARE LAST!") if danger else "")


func _last_position() -> int:
	var worst := 0
	for c in alive:
		worst = maxi(worst, int(race.racers[c]["position"]))
	return worst


func title() -> String:
	if winner:
		return Lang.t("%s IS THE LAST ONE STANDING!") % race.short_name(winner)
	return Lang.t("KNOCKED OUT!")
