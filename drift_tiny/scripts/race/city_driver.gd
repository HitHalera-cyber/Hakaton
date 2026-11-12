class_name CityDriver
extends RefCounted
## CPU driver for the city. It drives along the street graph from junction to
## junction and throws the car sideways into the turns.
##  * "chase": hunt a target car (police, or the bomb carrier): straight at it
##    when the street between is clear, otherwise along the shortest path.
##  * "flee": run from threats (robbers, everyone without the bomb): picks a
##    junction far from all threats that it can reach first, prefers routes
##    away from them, and grabs cash on the way.
##  * "cruise": wander to random junctions.

var city: TrackData
var mode := "cruise"
var target: Car                  # chase
var threats: Array = []          # flee: cars to run from
var goodies: Array = []          # flee: positions worth visiting (cash)
var skill := 1.0                 # top speed share
var enabled := true

var _path: Array = []
var _direct := false
var _aim := Vector2.ZERO
var _replan := 0.0
var _rev_t := 0.0
var _stuck := 0.0
var _hb_t := 0.0
var _mark := Vector2.ZERO        # where the car was at the last progress check
var _mark_t := 0.0
var _goal := -1                  # flee: junction we are heading for
var _rng := RandomNumberGenerator.new()


func _init(data: TrackData, seed_value := 0, skill_level := 1.0) -> void:
	city = data
	skill = skill_level
	_rng.seed = seed_value


func update_inputs(car: Car, delta: float) -> void:
	if not enabled or car.out:
		car.input_throttle = 0.0
		car.input_brake = 0.0
		car.input_steer = 0.0
		car.input_handbrake = false
		return
	_replan -= delta
	if _replan <= 0.0 or _path.is_empty() and not _direct:
		_replan = 0.35 + _rng.randf() * 0.15
		_plan(car)
	var p := car.global_position
	var aim := _aim
	var next_turn := 0.0
	var dist_to_aim := p.distance_to(aim)
	if not _direct and not _path.is_empty():
		aim = city.nodes[int(_path[0])]
		dist_to_aim = p.distance_to(aim)
		if dist_to_aim < 46.0 and _path.size() > 1:
			_path.pop_front()
			aim = city.nodes[int(_path[0])]
			dist_to_aim = p.distance_to(aim)
		if _path.size() > 1:
			var after: Vector2 = city.nodes[int(_path[1])]
			next_turn = absf((aim - p).angle_to(after - aim))
		elif dist_to_aim < 46.0:
			_replan = 0.0
	# Reverse out of walls.
	if _rev_t > 0.0:
		_rev_t -= delta
		car.input_throttle = 0.0
		car.input_brake = 1.0
		car.input_handbrake = false
		car.input_steer = -signf(wrapf((aim - p).angle() - car.rotation, -PI, PI))
		return
	var diff := wrapf((aim - p).angle() - car.rotation, -PI, PI)
	car.input_steer = clampf(diff * 2.6, -1.0, 1.0)
	if car.drifting and car.velocity.length() > 30.0:
		var vel_ang := car.velocity.angle()
		var beta := wrapf(car.rotation - vel_ang, -PI, PI)
		var want := clampf(wrapf((aim - p).angle() - vel_ang, -PI, PI) * 1.6, -0.7, 0.7)
		car.input_steer = clampf((want - beta) * 2.4, -1.0, 1.0)
	var top := car.stats.max_speed * skill
	var want_speed := top
	if not _direct and next_turn > 0.6 and dist_to_aim < 170.0:
		want_speed = lerpf(top, 135.0, clampf(next_turn / 1.6, 0.0, 1.0))
	if absf(diff) > 1.3:
		want_speed = minf(want_speed, 110.0)
	if car.speed < want_speed:
		car.input_throttle = 1.0
		car.input_brake = 0.0
	else:
		car.input_throttle = 0.2
		car.input_brake = clampf((car.speed - want_speed) / 90.0, 0.0, 1.0)
	# Handbrake flick into junction turns: drifting around the corner.
	if _hb_t > 0.0:
		_hb_t -= delta
		car.input_handbrake = true
	else:
		car.input_handbrake = false
		var turning := (not _direct and next_turn > 0.8 and dist_to_aim < 70.0) or absf(diff) > 0.7
		if turning and car.speed > 120.0 and not car.drifting:
			_hb_t = 0.2
	# Stuck against a building (hardly moved for a while): back off.
	_mark_t += delta
	if car.frozen:
		_mark_t = 0.0
		_mark = p
	elif _mark_t > 1.0:
		if p.distance_to(_mark) < 25.0:
			_rev_t = 0.8
		_mark_t = 0.0
		_mark = p


func _plan(car: Car) -> void:
	var p := car.global_position
	var here := city.nearest_node(p)
	match mode:
		"chase":
			if target == null or not is_instance_valid(target):
				_cruise(here)
				return
			var tp := target.global_position
			var d := p.distance_to(tp)
			if d < 420.0 and city.clear_line(p, tp):
				_direct = true
				# Lead the target a little.
				_aim = tp + target.velocity * clampf(d / 500.0, 0.05, 0.5)
				_path.clear()
				return
			_direct = false
			_path = city.city_path(_start_node(car, here), city.nearest_node(tp))
		"flee":
			_direct = false
			var avoid: Array = []
			for th in threats:
				if is_instance_valid(th) and not (th as Car).out:
					avoid.append((th as Car).global_position)
			if avoid.is_empty():
				_cruise(here)
				return
			var near_threat := INF
			for a: Vector2 in avoid:
				near_threat = minf(near_threat, a.distance_to(p))
			var best := here
			var best_score := -INF
			var goal_score := -INF
			for k in city.nodes.size():
				var sc := _flee_score(k, p, avoid, near_threat)
				if k == _goal:
					goal_score = sc
				if sc > best_score:
					best_score = sc
					best = k
			# Stick to the current getaway plan unless a clearly better one
			# shows up (switching every half second makes the car dither).
			if _goal >= 0 and goal_score > -INF and goal_score > best_score - 250.0 and p.distance_to(city.nodes[_goal]) > 60.0:
				best = _goal
			_goal = best
			# Keep going the way the car faces; turn around (handbrake U-turn)
			# only when the junction ahead is close to a threat.
			var start := _start_node(car, here)
			for a: Vector2 in avoid:
				if a.distance_to(city.nodes[start]) < 260.0:
					start = here
					break
			_path = city.city_path(start, best, avoid)
			if _path.size() > 1 and p.distance_to(city.nodes[int(_path[0])]) < 50.0:
				_path.pop_front()
		_:
			_direct = false
			if _path.size() <= 1:
				_cruise(here)


## How good junction k is as a getaway goal (-INF: a threat gets there first).
## With the cops far away the robber goes shopping for cash instead.
func _flee_score(k: int, p: Vector2, avoid: Array, near_threat: float) -> float:
	var np := city.nodes[k]
	var me := p.distance_to(np)
	var them := INF
	for a: Vector2 in avoid:
		them = minf(them, a.distance_to(np))
	if me > them * 0.85 and me > 120.0:
		return -INF
	var score := minf(them, 900.0) - me * 0.25
	# Edge and corner junctions are dead ends to get cornered in.
	score -= (4 - (city.links[k] as Array).size()) * 220.0
	var cash_w := 600.0 if near_threat > 650.0 else 160.0
	for g: Vector2 in goodies:
		var gd := g.distance_to(np)
		if gd < 200.0:
			score += cash_w * (1.0 - gd / 400.0)
	return score


func _cruise(here: int) -> void:
	_direct = false
	_path = city.city_path(here, _rng.randi_range(0, city.nodes.size() - 1))


## Start from the junction ahead of the car, not one behind it.
func _start_node(car: Car, here: int) -> int:
	var fwd := Vector2.from_angle(car.rotation)
	var to := city.nodes[here] - car.global_position
	if to.length() < 50.0 or to.dot(fwd) > 0.0:
		return here
	var best := here
	var best_d := -INF
	for m in city.links[here]:
		var v: Vector2 = city.nodes[int(m)] - car.global_position
		var dd := v.normalized().dot(fwd)
		if dd > best_d:
			best_d = dd
			best = int(m)
	return best
