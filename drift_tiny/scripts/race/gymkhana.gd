class_name Gymkhana
extends RefCounted
## Trick scoring on the gymkhana lot. A donut is a full drifting circle
## around one post; two donuts in opposite directions around two different
## posts, one right after the other, make a figure eight. A ramp jump scores
## too. Points go straight into the car's drift total.

const RANGE := 85.0
const DONUT_POINTS := 400
const EIGHT_BONUS := 1200
const AIR_POINTS := 250

var car: Car
var posts: Array = []
var donuts := 0
var eights := 0
var jumps := 0
var _post := -1
var _acc := 0.0
var _last_ang := 0.0
var _last_post := -1
var _last_dir := 0
var _since_donut := 99.0


func _init(the_car: Car, the_posts: Array) -> void:
	car = the_car
	posts = the_posts
	car.jumped.connect(_on_jump)


func _on_jump() -> void:
	jumps += 1
	_award(Lang.t("AIR"), AIR_POINTS)


func update(dt: float) -> void:
	_since_donut += dt
	var p := car.global_position
	var best := -1
	var best_d := RANGE
	for k in posts.size():
		var d := p.distance_to(posts[k])
		if d < best_d:
			best_d = d
			best = k
	if best < 0 or not car.drifting or car.speed < 40.0:
		_acc = move_toward(_acc, 0.0, dt * 2.0)
		if best < 0:
			_post = -1
		return
	var ang := (p - (posts[best] as Vector2)).angle()
	if best != _post:
		_post = best
		_acc = 0.0
		_last_ang = ang
		return
	_acc += wrapf(ang - _last_ang, -PI, PI)
	_last_ang = ang
	if absf(_acc) >= TAU:
		var dir := 1 if _acc > 0.0 else -1
		_acc -= dir * TAU
		donuts += 1
		_award(Lang.t("DONUT"), DONUT_POINTS + 80 * mini(donuts, 10))
		if _last_post >= 0 and _last_post != best and dir != _last_dir and _since_donut < 5.0:
			eights += 1
			_award(Lang.t("FIGURE EIGHT!"), EIGHT_BONUS)
		_last_post = best
		_last_dir = dir
		_since_donut = 0.0


## Current progress around the post, 0..1 (for the HUD).
func donut_progress() -> float:
	return absf(_acc) / TAU


func _award(text: String, pts: int) -> void:
	car.scoring.total += pts
	car.scoring.popup.emit(text, pts, "bank")
