class_name AutopilotController
extends RefCounted
## CPU driver: follows the centre line with a look-ahead point, slows for
## corners and throws in a handbrake flick on the tightest ones. Used by
## championship rivals and by the attract-mode car in the main menu.

var skill := 1.0          # 0.8 .. 1.1, scales target speeds
var lane := 0.0           # preferred offset from the centre line, px
var drift_happy := 0.5    # chance to use the handbrake in tight corners
var enabled := true

var _hb_t := 0.0
var _rng := RandomNumberGenerator.new()


func _init(skill_level := 1.0, lane_offset := 0.0, seed_value := 0) -> void:
	skill = skill_level
	lane = lane_offset
	_rng.seed = seed_value


func update_inputs(car: Car, delta: float) -> void:
	if not enabled or car.track == null:
		car.input_throttle = 0.0
		car.input_brake = 0.0
		car.input_steer = 0.0
		car.input_handbrake = false
		return
	var t := car.track
	var idx := car.track_idx if car.track_idx >= 0 else t.nearest(car.global_position)
	var look := clampf(car.speed * 0.32, 22.0, 80.0)
	var ahead := t.advance(idx, look)
	var target := t.samples[ahead] + t.normals[ahead] * lane
	var to := target - car.global_position
	var diff := wrapf(to.angle() - car.rotation, -PI, PI)
	car.input_steer = clampf(diff * 2.6, -1.0, 1.0)
	if car.drifting and car.velocity.length() > 30.0:
		# Cascade: choose the drift angle that bends the path towards the
		# target, then steer to hold it (this includes counter-steering).
		var vel_ang := car.velocity.angle()
		var beta := wrapf(car.rotation - vel_ang, -PI, PI)
		var want := clampf(wrapf(to.angle() - vel_ang, -PI, PI) * 1.5, -0.6, 0.6)
		car.input_steer = clampf((want - beta) * 2.5, -1.0, 1.0)

	# How hard is the road ahead?
	var bend := 0.0
	for k in [1, 2, 3, 4]:
		var j := t.advance(idx, look * 0.6 * k)
		bend = maxf(bend, absf(t.curvature[j]))
	var radius := 1.0 / maxf(bend, 0.0001)
	var max_s := car.stats.max_speed * skill
	var target_speed := clampf(sqrt(radius) * 15.0 * skill, 90.0, max_s) * sqrt(car.grip_now)
	if car.drifting:
		target_speed *= 0.85
	if car.speed < target_speed:
		car.input_throttle = 1.0
		car.input_brake = 0.0
	elif car.speed > target_speed + 25.0:
		car.input_throttle = 0.0
		car.input_brake = clampf((car.speed - target_speed) / 80.0, 0.2, 1.0)
	else:
		car.input_throttle = 0.4
		car.input_brake = 0.0
	# Handbrake flick into tight corners.
	if _hb_t > 0.0:
		_hb_t -= delta
		car.input_handbrake = true
	else:
		car.input_handbrake = false
		if radius < 120.0 and car.speed > 150.0 and absf(diff) > 0.25 and _rng.randf() < drift_happy * delta * 6.0:
			_hb_t = 0.22
	# Never sit still against a wall: reverse out.
	if car.speed < 10.0 and absf(diff) > 1.6:
		car.input_throttle = 0.0
		car.input_brake = 1.0
		car.input_steer = -car.input_steer
