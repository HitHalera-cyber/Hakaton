class_name PlayerController
extends RefCounted
## Reads one player's input actions (p1_* / p2_*) into the car.
## In a single-player race both layouts drive the same car, so either
## WASD or the arrows (or any pad) work.

var player_index := 1
var merge_both := false
var enabled := true


func _init(index: int, merge := false) -> void:
	player_index = index
	merge_both = merge


func update_inputs(car: Car, _delta: float) -> void:
	if not enabled:
		car.input_throttle = 0.0
		car.input_brake = 0.0
		car.input_steer = 0.0
		car.input_handbrake = false
		return
	var prefixes := ["p1_", "p2_"] if merge_both else ["p%d_" % player_index]
	var thr := 0.0
	var brk := 0.0
	var steer := 0.0
	var hb := false
	var reset := false
	for p in prefixes:
		thr = maxf(thr, Input.get_action_strength(p + "accel"))
		brk = maxf(brk, Input.get_action_strength(p + "brake"))
		var s := Input.get_axis(p + "left", p + "right")
		if absf(s) > absf(steer):
			steer = s
		hb = hb or Input.is_action_pressed(p + "handbrake")
		reset = reset or Input.is_action_just_pressed(p + "reset")
	car.input_throttle = thr
	car.input_brake = brk
	car.input_steer = steer
	car.input_handbrake = hb
	if reset and not car.frozen:
		car.respawn()
