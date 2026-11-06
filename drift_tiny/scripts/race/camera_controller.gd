class_name CameraController
extends Camera2D
## Top-down camera: no rotation, no perspective. Follows one car with a little
## look-ahead, or frames several cars at once (shared-screen two-player mode).

var targets: Array = []
var min_zoom := 0.6
var follow_speed := 6.0
var lookahead := 0.32
var shake_enabled := true
## Post shader of this view. The camera itself moves in whole pixels (so the
## low-res world never shimmers); the leftover fraction is applied by the
## shader as a sub-pixel shift, which makes scrolling smooth.
var post_material: ShaderMaterial

var _shake := 0.0
var _rng := RandomNumberGenerator.new()
var _focus := Vector2.ZERO


func _ready() -> void:
	ignore_rotation = true
	position_smoothing_enabled = false
	enabled = true


func set_bounds(r: Rect2) -> void:
	limit_left = int(r.position.x)
	limit_top = int(r.position.y)
	limit_right = int(r.end.x)
	limit_bottom = int(r.end.y)


func snap_to_targets() -> void:
	_focus = _desired()
	global_position = _focus


func shake(amount: float) -> void:
	if shake_enabled:
		_shake = maxf(_shake, amount)


func _desired() -> Vector2:
	if targets.is_empty():
		return global_position
	if targets.size() == 1:
		var car: Node2D = targets[0]
		var v: Vector2 = car.get("velocity") if "velocity" in car else Vector2.ZERO
		return _pos_of(car) + (v * lookahead).limit_length(70.0)
	var sum := Vector2.ZERO
	for t in targets:
		sum += _pos_of(t)
	return sum / targets.size()


## Smooth (interpolated) position of a target when it offers one.
func _pos_of(n: Node2D) -> Vector2:
	if n.has_method("visual_position"):
		return n.visual_position()
	return n.global_position


func _process(delta: float) -> void:
	_focus = _focus.lerp(_desired(), 1.0 - exp(-follow_speed * delta))
	if targets.size() > 1:
		_fit_zoom(delta)
	var off := Vector2.ZERO
	if _shake > 0.01:
		off = Vector2(_rng.randf_range(-1, 1), _rng.randf_range(-1, 1)) * _shake
		_shake = move_toward(_shake, 0.0, delta * 10.0)
	# Whole pixels keep the low-res world from shimmering; the shader adds the
	# remaining fraction back.
	var exact := _focus + off
	global_position = exact.round()
	if post_material:
		var frac := (exact - global_position) * zoom.x
		# At the track edge the camera limits stop it: no shift there.
		if get_screen_center_position().distance_to(global_position) > 0.5:
			frac = Vector2.ZERO
		post_material.set_shader_parameter("subpixel", frac)


func _fit_zoom(delta: float) -> void:
	var view := get_viewport_rect().size
	var r := Rect2((targets[0] as Node2D).global_position, Vector2.ZERO)
	for t in targets:
		r = r.expand((t as Node2D).global_position)
	r = r.grow(60.0)
	var z := minf(view.x / maxf(r.size.x, 1.0), view.y / maxf(r.size.y, 1.0))
	z = clampf(z, min_zoom, 1.0)
	var cur := lerpf(zoom.x, z, 1.0 - exp(-3.0 * delta))
	zoom = Vector2(cur, cur)


## True if all targets fit on screen at the widest allowed zoom.
func targets_fit() -> bool:
	if targets.size() < 2:
		return true
	var view := get_viewport_rect().size / min_zoom
	var r := Rect2((targets[0] as Node2D).global_position, Vector2.ZERO)
	for t in targets:
		r = r.expand((t as Node2D).global_position)
	return r.size.x < view.x - 40.0 and r.size.y < view.y - 40.0
