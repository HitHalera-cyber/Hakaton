class_name Weather
extends Node2D
## Screen-space weather for one view: rain streaks, snowfall, falling blossom
## petals or forest dust. Lives in a CanvasLayer inside the view's SubViewport,
## so it is drawn at the same low resolution as the world.

var kind := "none"
var camera: Camera2D
var _parts: Array = []
var _rng := RandomNumberGenerator.new()
var _last_cam := Vector2.ZERO
var _flash := 0.0


func setup(weather_kind: String, cam: Camera2D) -> void:
	kind = weather_kind
	camera = cam
	_rng.seed = randi()
	var count := 0
	match kind:
		"rain":
			count = 140
		"snow":
			count = 120
		"petals":
			count = 26
		"dust":
			count = 30
	for i in count:
		_parts.append(_spawn(true))


func _spawn(anywhere: bool) -> Dictionary:
	var size := get_viewport_rect().size
	var p := Vector2(_rng.randf() * size.x, _rng.randf() * size.y if anywhere else -4.0)
	var v := Vector2.ZERO
	match kind:
		"rain":
			v = Vector2(-40, 260) * _rng.randf_range(0.8, 1.2)
		"snow":
			v = Vector2(_rng.randf_range(-12, 6), _rng.randf_range(18, 40))
		"petals":
			v = Vector2(_rng.randf_range(8, 22), _rng.randf_range(10, 22))
		"dust":
			v = Vector2(_rng.randf_range(-6, 6), _rng.randf_range(-4, 4))
	return {"p": p, "v": v, "s": _rng.randf_range(0.6, 1.4), "ph": _rng.randf() * TAU}


func _process(delta: float) -> void:
	if kind == "none":
		return
	var size := get_viewport_rect().size
	# Particles drift against camera motion so they feel part of the world.
	var cam_delta := Vector2.ZERO
	if camera:
		cam_delta = camera.global_position - _last_cam
		_last_cam = camera.global_position
		if cam_delta.length() > 100.0:
			cam_delta = Vector2.ZERO
	var parallax := 0.6 if kind == "rain" else 1.0
	for d in _parts:
		var ph: float = d["ph"] + delta * 2.0
		d["ph"] = ph
		var v: Vector2 = d["v"]
		var sway := Vector2(sin(ph) * 8.0, 0.0) if kind in ["snow", "petals"] else Vector2.ZERO
		var p: Vector2 = d["p"] + (v + sway) * delta - cam_delta * parallax
		if p.y > size.y + 6.0 or p.x < -10.0 or p.x > size.x + 10.0 or p.y < -10.0:
			var n := _spawn(false)
			if p.x < -10.0:
				n["p"] = Vector2(size.x + 4.0, _rng.randf() * size.y)
			elif p.x > size.x + 10.0:
				n["p"] = Vector2(-4.0, _rng.randf() * size.y)
			elif p.y < -10.0:
				n["p"] = Vector2(_rng.randf() * size.x, size.y + 4.0)
			d.merge(n, true)
		else:
			d["p"] = p
	if kind == "rain" and _rng.randf() < delta * 0.05:
		_flash = 0.5
	_flash = move_toward(_flash, 0.0, delta * 2.0)
	queue_redraw()


func _draw() -> void:
	match kind:
		"rain":
			for d in _parts:
				var p: Vector2 = d["p"]
				var s: float = d["s"]
				draw_line(p, p + Vector2(-1.2, 6.0) * s, Color(0.7, 0.75, 1.0, 0.45), 1.0)
			if _flash > 0.0:
				draw_rect(get_viewport_rect(), Color(0.8, 0.8, 1.0, _flash * 0.25))
		"snow":
			for d in _parts:
				var p: Vector2 = d["p"]
				var s: float = d["s"]
				draw_rect(Rect2(p.floor(), Vector2.ONE * (2.0 if s > 1.1 else 1.0)), Color(1, 1, 1, 0.85))
		"petals":
			for d in _parts:
				var p: Vector2 = d["p"]
				var flip := sin(float(d["ph"]) * 2.0) > 0.0
				draw_rect(Rect2(p.floor(), Vector2(2, 1) if flip else Vector2(1, 2)), Color("f7a6cf"))
		"dust":
			for d in _parts:
				var p: Vector2 = d["p"]
				draw_rect(Rect2(p.floor(), Vector2.ONE), Color(1.0, 0.95, 0.7, 0.35 + 0.3 * sin(float(d["ph"]))))


static func kind_for_theme(theme: String) -> String:
	match theme:
		"neon":
			return "rain"
		"snow":
			return "snow"
		"mountain":
			return "petals"
		"forest":
			return "dust"
	return "none"
