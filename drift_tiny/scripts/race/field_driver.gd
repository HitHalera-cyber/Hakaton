class_name FieldDriver
extends RefCounted
## CPU driver for open maps (stadium, sumo ring): drives to the point the
## game sets in `aim` every tick, whips the car round with the handbrake,
## backs out of walls. want_speed caps the speed (careful on the ring edge).

var aim := Vector2.ZERO
var want_speed := 9999.0
var skill := 1.0
var enabled := true

var _rev_t := 0.0
var _hb_t := 0.0
var _mark := Vector2.ZERO
var _mark_t := 0.0


func _init(skill_level := 1.0) -> void:
	skill = skill_level


func update_inputs(car: Car, delta: float) -> void:
	if not enabled or car.out:
		car.input_throttle = 0.0
		car.input_brake = 0.0
		car.input_steer = 0.0
		car.input_handbrake = false
		return
	var p := car.global_position
	var to := aim - p
	var diff := wrapf(to.angle() - car.rotation, -PI, PI)
	if _rev_t > 0.0:
		_rev_t -= delta
		car.input_throttle = 0.0
		car.input_brake = 1.0
		car.input_handbrake = false
		car.input_steer = -signf(diff)
		return
	car.input_steer = clampf(diff * 2.8, -1.0, 1.0)
	var top := minf(car.stats.max_speed * skill, want_speed)
	# Target right behind us and close: a quick reverse turn is faster.
	if absf(diff) > 2.3 and to.length() < 70.0 and car.speed < 90.0:
		_rev_t = 0.5
	if car.speed < top:
		car.input_throttle = 1.0 if absf(diff) < 1.6 else 0.6
		car.input_brake = 0.0
	else:
		car.input_throttle = 0.0
		car.input_brake = clampf((car.speed - top) / 80.0, 0.1, 1.0)
	if _hb_t > 0.0:
		_hb_t -= delta
		car.input_handbrake = true
	else:
		car.input_handbrake = false
		if absf(diff) > 0.9 and car.speed > 110.0 and not car.drifting:
			_hb_t = 0.25
	_mark_t += delta
	if car.frozen:
		_mark_t = 0.0
		_mark = p
	elif _mark_t > 1.0:
		if p.distance_to(_mark) < 20.0 and to.length() > 30.0:
			_rev_t = 0.7
		_mark_t = 0.0
		_mark = p
