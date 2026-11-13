class_name Car
extends CharacterBody2D
## Arcade top-down car with a controllable drift.
##
## Model: velocity is split into a longitudinal and a lateral part in the car's
## frame. Engine, brakes and drag act on the longitudinal part; grip kills the
## lateral part exponentially. Grip drops while drifting (handbrake, or power
## oversteer on cars with power_slide), so the heading can run ahead of the
## velocity — the angle between them is the slip angle that scores points.
## tools/sim_drift.py is an offline copy of this model used for tuning.

signal crashed(impact: float, at: Vector2)
signal bumped(other: Car, impact: float)
signal respawned
signal boosted(level: int)

const DRAG := 0.22
const ROLL := 35.0
const PX_TO_KMH := 0.6
const DRIFT_YAW := 2.8         # rad/s of yaw per full steer while drifting (x drift_steer)
const POWER_YAW := 1.4         # how hard throttle pushes the rear out (x power_slide)
const ALIGN := 1.2             # tyres pulling the drift angle back to zero
const HB_YAW := 2.4            # extra pivot while the handbrake is held
const DRIFT_FRICTION := 130.0  # sideways deceleration of sliding tyres (x drift_grip)
# Drift boost ("mini-turbo"): seconds of drifting needed for levels 1..3, and
# what each level gives when the drift ends cleanly.
const BOOST_CHARGE := [0.5, 1.2, 2.2]
const BOOST_POWER := [0.15, 0.25, 0.35]
const BOOST_TIME := [0.6, 0.9, 1.3]
const BOOST_COLORS := [Color("3ee0ff"), Color("ffae2a"), Color("ff5fb8")]

var stats: CarStats
var controller: Object = null      # anything with update_inputs(car, delta)
var track: TrackData
var skids: SkidLayer
var player_index := 0               # 1 / 2 for humans, 0 for CPU
var display_name := ""
var tag_color := Color.WHITE
var siren := false                  # police light bar on the roof
var badge := ""                     # small text above the tag (bomb timer, "$")
var badge_color := Color.WHITE
var out := false                    # busted / knocked out: parked, no collisions
var night := false

# Inputs, written by the controller every physics frame.
var input_throttle := 0.0
var input_brake := 0.0
var input_steer := 0.0
var input_handbrake := false

# State.
var frozen := true
var replaying := false       # pose comes from the best-drift replay
var drifting := false
var slip_deg := 0.0
var speed := 0.0
var angular := 0.0
var steer_visual := 0.0
var rpm := 0.2
var track_idx := -1
var lateral_off := 0.0
var on_road := true
var edge_dist := 99.0
var surface_name := "asphalt"
var distance_driven := 0.0
var braking_visual := false
var grip_now := 1.0
var scoring := DriftScoring.new()
var drift_charge := 0.0      # seconds of good drifting in the current slide
var boost_t := 0.0
var boost_level := 0

var _exit_t := 0.0
var _stuck_t := 0.0
var _bump_cd := 0.0
var _ghost_t := 0.0
var _last_wheels: Array = []
var _skid_on := false
var _smoke: Array = []
var _sparks: CPUParticles2D
var _light: Sprite2D
var _shake_cb: Callable
var _outline := GraphicsStyle.flag("outline")
var _boost_power := 0.0
var _pad_cd := 0.0
var hazard := ""             # hazard under the car this frame
var air_t := 0.0             # > 0 while flying off a ramp
var touches := 0             # barrier contacts (for the clean-lap challenge)
const AIR_TIME := 0.6
signal jumped
var _charge_fx: CPUParticles2D
# Physics runs at 60 Hz; the car is drawn between the last two physics
# positions so motion stays smooth at any frame rate.
var _prev_pos := Vector2.ZERO
var _floats: Array = []      # score texts rising above the car: {text, color, t}
var _prev_rot := 0.0


func setup(car_stats: CarStats, track_data: TrackData, skid_layer: SkidLayer) -> void:
	stats = car_stats
	track = track_data
	skids = skid_layer
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	wall_min_slide_angle = deg_to_rad(5.0)
	collision_layer = 2
	collision_mask = 1 | 2 | 4   # 4: drift-only shortcut gates
	safe_margin = 0.5
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(stats.length - 1.0, stats.width - 1.0)
	shape.shape = rect
	add_child(shape)
	z_index = 5
	for side in [-1.0, 1.0]:
		var p := _make_smoke()
		p.position = Vector2(-stats.length * 0.5 + 2.0, side * stats.width * 0.4)
		add_child(p)
		_smoke.append(p)
	_sparks = _make_sparks()
	add_child(_sparks)
	scoring.popup.connect(_on_score_popup)
	_charge_fx = _make_charge_fx()
	_charge_fx.position = Vector2(-stats.length * 0.5, 0)
	add_child(_charge_fx)
	if night or Game.quality() > 0:
		# Headlight beam: additive sprite, no 2D lights needed. Visible at
		# night or when the day cycle gets dark.
		_light = Sprite2D.new()
		_light.texture = FxTextures.headlight_cone()
		_light.centered = false
		_light.offset = Vector2(0, -24)
		_light.position = Vector2(stats.length * 0.5 - 1.0, 0)
		_light.scale = Vector2(1.1, 0.9)
		_light.modulate = Color(1.0, 0.95, 0.75, 0.55)
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		_light.material = mat
		_light.z_index = 1
		add_child(_light)


## Puts the car on the grid. Works before the car is inside the tree
## (cars are direct children of the world node, which sits at the origin).
func place(pos: Vector2, rot: float) -> void:
	position = pos
	rotation = rot
	_prev_pos = pos
	_prev_rot = rot
	velocity = Vector2.ZERO
	angular = 0.0
	drifting = false
	track_idx = -1
	_last_wheels.clear()
	_update_track()


func set_shake_callback(cb: Callable) -> void:
	_shake_cb = cb


# --- physics ----------------------------------------------------------------

## Where the car is drawn this frame (between the last two physics steps).
func visual_transform() -> Transform2D:
	var a := Engine.get_physics_interpolation_fraction()
	var pos := global_position if is_inside_tree() else position
	return Transform2D(lerp_angle(_prev_rot, rotation, a), _prev_pos.lerp(pos, a))


func visual_position() -> Vector2:
	return visual_transform().origin


func _snap_interpolation() -> void:
	_prev_pos = global_position
	_prev_rot = rotation


func _process(delta: float) -> void:
	queue_redraw()
	for f in _floats:
		f["t"] = float(f["t"]) + delta
	while not _floats.is_empty() and float(_floats[0]["t"]) > 1.2:
		_floats.pop_front()
	if _light:
		_light.visible = night or Game.darkness > 0.35
		var local := get_global_transform().affine_inverse() * visual_transform()
		_light.transform = local * Transform2D(0.0, Vector2(1.1, 0.9), 0.0, Vector2(stats.length * 0.5 - 1.0, 0))


func _physics_process(delta: float) -> void:
	if replaying:
		# The race sets the pose from the recording (and the previous pose).
		_set_smoke(drifting and slip_deg > 8.0)
		queue_redraw()
		return
	_prev_pos = global_position
	_prev_rot = rotation
	if controller != null:
		controller.update_inputs(self, delta)
	_bump_cd = maxf(_bump_cd - delta, 0.0)
	if _ghost_t > 0.0:
		_ghost_t -= delta
		modulate.a = 0.45 if int(_ghost_t * 12.0) % 2 == 0 else 0.8
		if _ghost_t <= 0.0:
			_set_ghosting(false)
	if frozen:
		velocity = Vector2.ZERO
		speed = 0.0
		rpm = lerpf(rpm, 0.25 + input_throttle * 0.7, 1.0 - exp(-6.0 * delta))
		_set_smoke(false)
		queue_redraw()
		return
	_step_handling(delta)
	# Shortcut gates open only for a car that is sliding.
	set_collision_mask_value(3, not drifting)
	var pre := velocity
	move_and_slide()
	_handle_collisions(pre)
	_update_track()
	_check_hazards(delta)
	_check_stuck(delta)
	_update_fx()
	distance_driven += velocity.length() * delta
	scoring.update(delta, self)
	queue_redraw()


func _step_handling(dt: float) -> void:
	var st := stats
	var fwd := Vector2.from_angle(rotation)
	var right := Vector2(-fwd.y, fwd.x)
	var vl := velocity.dot(fwd)
	var vt := velocity.dot(right)
	speed = velocity.length()
	var surf := _surface()
	var grip_mult: float = surf["grip"]
	grip_now = grip_mult
	if boost_t > 0.0:
		boost_t -= dt
	var boost := _boost_power if boost_t > 0.0 else 0.0
	var maxs: float = st.max_speed * float(surf["speed"]) * (1.0 + boost)
	var thr := input_throttle
	var brk := input_brake
	var steer := input_steer
	var hb := input_handbrake

	if thr > 0.0:
		if vl < -5.0:
			vl += st.brake * thr * dt
		else:
			var f := maxf(0.0, 1.0 - pow(maxf(vl, 0.0) / maxs, 2.0))
			vl += st.accel * (1.0 + boost * 3.0) * thr * f * dt
	if brk > 0.0:
		if vl > 5.0:
			vl -= st.brake * brk * dt
		else:
			vl = maxf(vl - st.accel * 0.5 * brk * dt, -maxs * 0.35)
	vl -= vl * (DRAG + float(surf["drag"])) * dt
	if thr == 0.0 and brk == 0.0:
		vl = move_toward(vl, 0.0, ROLL * dt)
	if hb:
		vl = move_toward(vl, 0.0, st.brake * 0.3 * dt)
	braking_visual = brk > 0.1 and vl > 5.0

	# Angle between heading and travel: 0 straight, 90 sideways, 180 backwards.
	var slip_full := rad_to_deg(atan2(absf(vt), vl)) if speed > 1.0 else 0.0
	slip_deg = minf(slip_full, 90.0)

	# Drift state machine. Easy to start (handbrake from 50 px/s, or power
	# oversteer), and sticky: the slide only ends once the car is straight.
	var was_drifting := drifting
	if hb and speed > 50.0:
		drifting = true
	if not drifting and speed > maxs * 0.45 and absf(steer) > 0.7 and thr > 0.8 \
			and slip_deg > 13.0 - 10.0 * st.power_slide:
		drifting = true
	if drifting:
		if slip_deg < 7.0 and not hb:
			_exit_t += dt
			if _exit_t > 0.3:
				drifting = false
		else:
			_exit_t = 0.0
		if speed < 35.0:
			drifting = false

	# Yaw.
	var dir_sign := 1.0 if vl >= -2.0 else -1.0
	var sf := minf(absf(vl) / 70.0, 1.0)
	var target := 0.0
	var resp := 12.0
	if drifting:
		# Steering and throttle open the drift angle (beta), the tyres pull it
		# back towards zero, so a slide settles at an angle the player holds.
		var beta := wrapf(rotation - velocity.angle(), -PI, PI) if speed > 1.0 else 0.0
		target = steer * DRIFT_YAW * st.drift_steer * maxf(sf, 0.6)
		target += signf(beta) * thr * st.power_slide * POWER_YAW * minf(absf(beta) / 0.45, 1.0)
		var align := ALIGN / st.drift_stability
		if hb:
			# Locked rear wheels: the car pivots around the front.
			target += steer * HB_YAW
			align *= 0.3
		target -= align * beta
		resp = 6.0
	else:
		var hs := 1.0 - 0.45 * minf(speed / maxs, 1.0)
		target = steer * st.steer * sf * hs * dir_sign
	angular += (target - angular) * (1.0 - exp(-resp * dt))

	# Charge the drift boost while sliding well; release it when the slide ends.
	if drifting and slip_deg > 12.0 and speed > 60.0:
		drift_charge += dt
	if was_drifting and not drifting:
		_release_boost()

	if air_t > 0.0:
		# Flying: no grip, no steering, the car keeps its momentum and spin.
		angular *= 0.995
		rotation += angular * dt
		return
	# Lateral grip. Gripping tyres kill sideways speed exponentially; sliding
	# tyres give a roughly constant sideways force (past the grip peak), so a
	# slide can still follow a tight corner.
	var new_vt := 0.0
	var keep := 0.8
	if drifting:
		var acc := st.drift_grip * DRIFT_FRICTION * (0.55 if hb else 1.0) * grip_mult
		acc *= 1.0 + maxf(slip_deg - 50.0, 0.0) * 0.02 * st.drift_stability
		new_vt = move_toward(vt, 0.0, acc * dt)
		keep = st.drift_keep
	else:
		new_vt = vt * exp(-st.grip * grip_mult * dt)
	# Part of the sideways speed the tyres take away becomes forward speed
	# (energy-wise, so cornering never adds speed).
	if vl >= 0.0:
		vl = sqrt(vl * vl + (vt * vt - new_vt * new_vt) * keep)
	if drifting:
		vl -= vl * 0.35 * minf(slip_deg / 45.0, 1.5) * dt
	# Recompose in the frame the components were measured in; the heading
	# turns afterwards, which is what opens up the slip angle.
	velocity = fwd * vl + right * new_vt
	var cap := st.max_speed * 1.05 * (1.0 + boost)
	if velocity.length() > cap:
		velocity = velocity.normalized() * cap
	rotation += angular * dt
	steer_visual = lerpf(steer_visual, steer * 0.5, 0.3)

	# Spun out: no boost for that.
	if drifting and slip_full > 110.0:
		drifting = false
		drift_charge = 0.0
		scoring.fail("SPIN OUT")

	# Fake gearbox for the engine sound.
	var r := clampf(speed / st.max_speed, 0.0, 1.0)
	var gear := mini(int(r * 5.0), 4)
	var target_rpm := 0.3 + (r * 5.0 - gear) * 0.6
	if drifting and thr > 0.5:
		target_rpm = minf(target_rpm + 0.25, 1.0)
	if thr < 0.1:
		target_rpm *= 0.8
	rpm = lerpf(rpm, target_rpm, 1.0 - exp(-8.0 * dt))


## Grip / drag / top speed multipliers under the car.
func _surface() -> Dictionary:
	var grip := 1.0
	var drag := 0.0
	var spd := 1.0
	var loose := false
	if track == null:
		return {"grip": grip, "drag": drag, "speed": spd}
	if not on_road:
		match track.theme:
			"neon", "midnight":
				surface_name = "pavement"
			"desk":
				surface_name = "wood"
			"vector":
				surface_name = "grid"
			_:
				surface_name = "snowbank" if track.surface == "snow" else "grass"
		grip = 0.65
		drag = 1.6 if track.surface == "snow" else 1.2
		spd = 0.6
		loose = true
	else:
		surface_name = track.surface
		match track.surface:
			"wet":
				grip = 0.86
			"plastic":
				grip = 0.95
			"dirt":
				grip = 0.8
				loose = true
			"snow":
				grip = 0.72
				loose = true
		if track.is_ice(track_idx):
			surface_name = "ice"
			grip = 0.5
			loose = true
		match hazard:
			"oil":
				surface_name = "oil"
				grip = 0.3
			"gravel":
				surface_name = "gravel"
				grip *= 0.7
				drag += 1.4
				loose = true
			"ice":
				surface_name = "ice"
				grip = 0.5
				loose = true
	if Game.raining and track.surface in ["asphalt", "plastic"]:
		grip *= 0.88
	if loose and stats.loose_surface_bonus > 0.0:
		grip += (1.0 - grip) * stats.loose_surface_bonus
	return {"grip": grip, "drag": drag, "speed": spd}


func _handle_collisions(pre: Vector2) -> void:
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var n := c.get_normal()
		var other := c.get_collider()
		if other is Car:
			_bump_car(other as Car, n, pre)
			continue
		var impact := -pre.dot(n)
		if impact < 20.0:
			continue
		touches += 1
		velocity += n * impact * 0.35
		velocity *= 0.9 if impact < 90.0 else 0.72
		angular *= 0.5
		if impact > 70.0:
			_spark_at(c.get_position(), n)
			crashed.emit(impact, c.get_position())
			if _shake_cb.is_valid():
				_shake_cb.call(clampf(impact / 60.0, 1.0, 4.0))
		if impact > 110.0:
			scoring.fail("CRASH")
			drift_charge = 0.0
			boost_t = 0.0
		else:
			scoring.touch()


## Momentum exchange between two cars along the contact normal (n points from
## the other car towards this one). Predictable, no position correction.
func _bump_car(o: Car, n: Vector2, pre: Vector2) -> void:
	if _bump_cd > 0.0:
		return
	var rel := (pre - o.velocity).dot(n)
	if rel >= 0.0:
		return
	var m1 := stats.mass
	var m2 := o.stats.mass
	var j := -(1.0 + 0.35) * rel / (1.0 / m1 + 1.0 / m2)
	velocity += n * j / m1
	o.velocity -= n * j / m2
	_bump_cd = 0.12
	o._bump_cd = 0.12
	var impact := absf(rel)
	if impact > 60.0:
		_spark_at(global_position - n * stats.width * 0.5, n)
		scoring.touch()
		o.scoring.touch()
	bumped.emit(o, impact)


func _update_track() -> void:
	if track == null:
		return
	var p := global_position if is_inside_tree() else position
	track_idx = track.nearest(p, track_idx)
	lateral_off = track.lateral(p, track_idx)
	on_road = absf(lateral_off) <= track.width * 0.5 + 1.0
	edge_dist = track.width * 0.5 - absf(lateral_off)
	if not on_road and not track.shortcuts.is_empty() and track.in_shortcut(p):
		on_road = true
		edge_dist = 6.0


func _check_hazards(dt: float) -> void:
	_pad_cd = maxf(_pad_cd - dt, 0.0)
	hazard = track.hazard_at(global_position, track_idx) if track else ""
	if air_t > 0.0:
		air_t -= dt
	elif hazard == "ramp" and speed > 80.0:
		air_t = AIR_TIME
		jumped.emit()
		add_float("AIR!", Color("ffd84a"))
	if hazard == "boost" and _pad_cd <= 0.0:
		_pad_cd = 1.0
		boost_level = 2
		boost_t = 0.8
		_boost_power = 0.3
		boosted.emit(2)
		add_float("BOOST PAD", BOOST_COLORS[1])


func _check_stuck(dt: float) -> void:
	if controller == null:
		return
	if (input_throttle > 0.5 or input_brake > 0.5) and speed < 12.0:
		_stuck_t += dt
		if _stuck_t > 2.5:
			respawn()
	else:
		_stuck_t = 0.0


## Puts the car back on the centre line at the nearest point of the track.
func respawn() -> void:
	if track == null:
		return
	_stuck_t = 0.0
	scoring.fail("")
	if track.field == "sumo":
		return    # no rescue from the edge of the ring
	var pose := track.respawn_pose(global_position)
	global_position = pose["position"]
	rotation = pose["rotation"]
	velocity = Vector2.ZERO
	angular = 0.0
	drifting = false
	drift_charge = 0.0
	boost_t = 0.0
	_last_wheels.clear()
	_update_track()
	_snap_interpolation()
	_set_ghosting(true)
	respawned.emit()


## Used by the shared camera's catch-up: the car was moved by the race.
func respawn_soft() -> void:
	scoring.fail("")
	angular = 0.0
	drifting = false
	drift_charge = 0.0
	track_idx = -1
	_last_wheels.clear()
	_update_track()
	_snap_interpolation()
	_set_ghosting(true)


## Pixel text that rises above the car and fades (drift points, grades, boost).
func add_float(text: String, col: Color) -> void:
	_floats.append({"text": text, "color": col, "t": 0.0})
	if _floats.size() > 3:
		_floats.pop_front()


func _on_score_popup(_text: String, pts: int, kind: String) -> void:
	match kind:
		"bank":
			add_float("+%d" % pts, Color("ffd84a"))
		"zone":
			# World text uses the pixel font (Latin only): grade letter is the last char.
			add_float("ZONE %s +%d" % [_text.right(1), pts], Color("3ee0ff"))
		"fail":
			add_float("-%d" % pts, Color("ff5a5a"))


func charge_level() -> int:
	var lvl := 0
	for i in BOOST_CHARGE.size():
		if drift_charge >= BOOST_CHARGE[i]:
			lvl = i + 1
	return lvl


func _release_boost() -> void:
	var lvl := charge_level()
	drift_charge = 0.0
	if lvl == 0:
		return
	boost_level = lvl
	boost_t = BOOST_TIME[lvl - 1]
	_boost_power = BOOST_POWER[lvl - 1]
	boosted.emit(lvl)
	add_float("BOOST" + "!".repeat(lvl), BOOST_COLORS[lvl - 1])
	if _shake_cb.is_valid():
		_shake_cb.call(0.8 + lvl * 0.4)


func _set_ghosting(on: bool) -> void:
	_ghost_t = 1.5 if on else 0.0
	set_collision_layer_value(2, not on)
	set_collision_mask_value(2, not on)
	if not on:
		modulate.a = 1.0


func is_ghosting() -> bool:
	return _ghost_t > 0.0


func kmh() -> int:
	return int(speed * PX_TO_KMH)


# --- effects ------------------------------------------------------------------

func _update_fx() -> void:
	var sliding := (drifting and slip_deg > 8.0 and speed > 40.0) or (input_handbrake and speed > 60.0)
	var hard_brake := input_brake > 0.8 and speed > 120.0
	var loose := surface_name in ["dirt", "grass", "sand", "snow", "snowbank", "gravel"]
	_set_smoke(sliding or (loose and speed > 110.0 and input_throttle > 0.5))
	# Smoke colour follows the surface: white smoke, brown dust, snow spray.
	var col := Color(1, 1, 1, 0.75)
	if surface_name in ["dirt", "grass", "sand", "gravel"]:
		col = Color(0.62, 0.48, 0.32, 0.7)
	elif surface_name in ["snow", "snowbank", "ice"]:
		col = Color(0.92, 0.96, 1.0, 0.85)
	elif player_index > 0:
		# A hint of the player's colour makes each car's smoke its own.
		col = col.lerp(Color(tag_color, col.a), 0.3)
	for p in _smoke:
		(p as CPUParticles2D).color = col
	# Boost charge sparks under the rear: blue, orange, then pink.
	var lvl := charge_level()
	_charge_fx.emitting = drifting and lvl > 0
	if lvl > 0:
		_charge_fx.color = BOOST_COLORS[lvl - 1]
	if skids == null:
		return
	var wheels: Array = []
	for side in [-1.0, 1.0]:
		wheels.append(to_global(Vector2(-stats.length * 0.5 + 3.0, side * (stats.width * 0.5 - 0.5))))
	var mark := sliding or hard_brake
	if mark and _skid_on and _last_wheels.size() == 2:
		var a := clampf(slip_deg / 40.0, 0.35, 0.9) if sliding else 0.5
		for k in 2:
			skids.add(_last_wheels[k], wheels[k], a, surface_name)
	_skid_on = mark
	_last_wheels = wheels


func _set_smoke(on: bool) -> void:
	for p in _smoke:
		(p as CPUParticles2D).emitting = on


func _spark_at(pos: Vector2, normal: Vector2) -> void:
	_sparks.global_position = pos
	_sparks.direction = normal.rotated(-global_rotation)
	_sparks.restart()


func _make_smoke() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.amount = int(Game.by_quality([16, 36, 60]))
	p.lifetime = 1.2
	p.local_coords = false
	p.emitting = false
	p.texture = FxTextures.puff()
	p.direction = Vector2(-1, 0)
	p.spread = 40.0
	p.gravity = Vector2.ZERO
	p.initial_velocity_min = 6.0
	p.initial_velocity_max = 20.0
	p.damping_min = 8.0
	p.damping_max = 16.0
	p.scale_amount_min = 0.6
	p.scale_amount_max = 1.1
	var curve := Curve.new()
	curve.max_value = 3.0
	curve.add_point(Vector2(0.0, 0.6))
	curve.add_point(Vector2(1.0, 3.0)) # puffs grow into big clouds
	p.scale_amount_curve = curve
	var ramp := Gradient.new()
	ramp.set_color(0, Color(1, 1, 1, 0.8))
	ramp.set_color(1, Color(1, 1, 1, 0.0))
	p.color_ramp = ramp
	p.z_index = -1
	return p


func _make_charge_fx() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.amount = int(Game.by_quality([8, 14, 20]))
	p.lifetime = 0.3
	p.local_coords = false
	p.emitting = false
	p.texture = FxTextures.pixel()
	p.direction = Vector2(-1, 0)
	p.spread = 50.0
	p.gravity = Vector2.ZERO
	p.initial_velocity_min = 30.0
	p.initial_velocity_max = 70.0
	p.damping_min = 60.0
	p.damping_max = 100.0
	p.scale_amount_min = 0.5
	p.scale_amount_max = 1.0
	p.emission_shape = CPUParticles2D.EMISSION_SHAPE_RECTANGLE
	p.emission_rect_extents = Vector2(1, stats.width * 0.45)
	p.z_index = 1
	return p


func _make_sparks() -> CPUParticles2D:
	var p := CPUParticles2D.new()
	p.amount = 14
	p.lifetime = 0.35
	p.one_shot = true
	p.explosiveness = 1.0
	p.emitting = false
	p.local_coords = false
	p.spread = 70.0
	p.gravity = Vector2.ZERO
	p.initial_velocity_min = 40.0
	p.initial_velocity_max = 110.0
	p.damping_min = 80.0
	p.damping_max = 140.0
	p.scale_amount_min = 1.0
	p.scale_amount_max = 1.0
	var ramp := Gradient.new()
	ramp.set_color(0, Color(1.0, 0.95, 0.6, 1.0))
	ramp.set_color(1, Color(1.0, 0.4, 0.1, 0.0))
	p.color_ramp = ramp
	p.z_index = 2
	return p


# --- drawing --------------------------------------------------------------

func _draw() -> void:
	if stats == null:
		return
	# Draw at the interpolated pose, expressed in this node's local space.
	var vis := visual_transform()
	var inv := get_global_transform().affine_inverse()
	var base := inv * vis
	if air_t > 0.0:
		# Airborne: the car looks bigger (closer to the camera) mid-jump.
		var k := 1.0 + 0.35 * sin(PI * (1.0 - air_t / AIR_TIME))
		base = base * Transform2D(0.0, Vector2(k, k), 0.0, Vector2.ZERO)
	var shadow := inv * Transform2D(vis.get_rotation(), vis.origin + Vector2(1.5, 2.0))
	CarPainter.draw_shadow(self, shadow, stats.length, stats.width)
	if boost_t > 0.0:
		_draw_flame(base)
	CarPainter.draw_car(self, base, stats.shape, stats.length, stats.width,
			stats.color, stats.rims, stats.decal, steer_visual, braking_visual, 1.0, _outline)
	if siren:
		_draw_siren(base)
	if player_index > 0 or display_name != "":
		# Tag above the car, kept upright regardless of the car's rotation.
		draw_set_transform_matrix(inv * Transform2D(0.0, vis.origin + Vector2(0, -12)))
		draw_colored_polygon(PackedVector2Array([Vector2(-2.5, 3), Vector2(2.5, 3), Vector2(0, 6)]), tag_color)
		var tag := "%dP" % player_index if player_index > 0 else display_name
		PixelText.draw_centered(self, Vector2(0, -1), tag, tag_color)
		if badge != "":
			PixelText.draw_centered(self, Vector2(0, -8), badge, badge_color)
		for i in _floats.size():
			var f: Dictionary = _floats[i]
			var age: float = f["t"]
			var fc: Color = f["color"]
			fc.a = clampf(1.6 - age * 1.4, 0.0, 1.0)
			PixelText.draw_centered(self, Vector2(0, -9 - age * 14.0 - (_floats.size() - 1 - i) * 7), str(f["text"]), fc)
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## Police light bar: red and blue blink in turn, with a soft glow around.
func _draw_siren(base: Transform2D) -> void:
	draw_set_transform_matrix(base)
	var on := int(Time.get_ticks_msec() / 160) % 2 == 0
	var red := Color("ff3040")
	var blue := Color("3a7bff")
	var w := stats.width * 0.5 - 1.0
	draw_rect(Rect2(-1.5, -w, 3, w * 2.0), Color("1a1a22"))
	draw_rect(Rect2(-1.0, -w + 0.5, 2, w - 0.5), red if on else red.darkened(0.6))
	draw_rect(Rect2(-1.0, 0.0, 2, w - 0.5), blue.darkened(0.6) if on else blue)
	var glow := Color(red, 0.22) if on else Color(blue, 0.22)
	draw_circle(Vector2(0, -w * 0.5 if on else w * 0.5), 9.0, glow)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


## Exhaust flame while boosting: flickers and takes the boost level's colour.
func _draw_flame(base: Transform2D) -> void:
	var hl := stats.length * 0.5
	var flick := 0.7 + 0.3 * sin(Time.get_ticks_msec() * 0.06)
	var lvl_col: Color = BOOST_COLORS[clampi(boost_level - 1, 0, 2)]
	var flame_len := (5.0 + boost_level * 2.0) * flick
	draw_set_transform_matrix(base)
	for side in [-1.5, 1.5]:
		var y: float = side
		draw_colored_polygon(PackedVector2Array([Vector2(-hl, y - 1.5), Vector2(-hl - flame_len, y), Vector2(-hl, y + 1.5)]), lvl_col)
		draw_colored_polygon(PackedVector2Array([Vector2(-hl, y - 0.8), Vector2(-hl - flame_len * 0.55, y), Vector2(-hl, y + 0.8)]), Color("fff3b0"))
	draw_set_transform_matrix(Transform2D.IDENTITY)
