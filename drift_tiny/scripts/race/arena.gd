class_name Arena
extends RefCounted
## The gymkhana lot: a fenced asphalt square with donut posts, a slalom of
## cones, ramps, boost pads and an oil slick, ringed by spectators.


static func build(t: Track) -> void:
	var data := t.data
	var r := data.arena_rect
	# Collision: outer wall, posts and cones (static, layer 1).
	var body := StaticBody2D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	t.add_child(body)
	var w := PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
	var segs := PackedVector2Array()
	for k in 4:
		segs.append(w[k])
		segs.append(w[(k + 1) % 4])
	var wall := ConcavePolygonShape2D.new()
	wall.segments = segs
	var cs := CollisionShape2D.new()
	cs.shape = wall
	body.add_child(cs)
	for p in data.posts:
		_circle_body(body, p, 8.0)
	for p in data.cones:
		_circle_body(body, p, 3.0)
	# Crowd around the fence (the flashes fire whenever someone drifts).
	var shirts := [Color("e8313f"), Color("2f7ee8"), Color("f2c230"), Color("2fae5a"), Color("f4f4f4"), Color("ff5fb8")]
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	t.spectators.arena_mode = true
	var x := r.position.x + 10.0
	while x < r.end.x - 10.0:
		for row in 3:
			if rng.randf() < 0.75:
				t.spectators.add_person(Vector2(x + rng.randf_range(-2, 2), r.position.y - 10.0 - row * 6.0).round(), shirts[rng.randi_range(0, 5)], 0)
				t.spectators.add_person(Vector2(x + rng.randf_range(-2, 2), r.end.y + 10.0 + row * 6.0).round(), shirts[rng.randi_range(0, 5)], 0)
		x += 6.0
	t._add_layer("Ground", -10, func(ci: Node2D): Arena.draw_ground(t, ci), true)
	t._add_layer("Markings", -7, func(ci: Node2D): Arena.draw_markings(t, ci))
	t._add_layer("Scenery", 6, func(ci: Node2D): Arena.draw_props(t, ci))


static func _circle_body(body: StaticBody2D, p: Vector2, radius: float) -> void:
	var shape := CircleShape2D.new()
	shape.radius = radius
	var cs := CollisionShape2D.new()
	cs.shape = shape
	cs.position = p
	body.add_child(cs)


static func draw_ground(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var r := data.arena_rect
	tb.rect(data.bounds, Color("3a5a34"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 9
	for i in 1500:
		var p := Vector2(rng.randf_range(data.bounds.position.x, data.bounds.end.x), rng.randf_range(data.bounds.position.y, data.bounds.end.y))
		tb.rect(Rect2(p.floor(), Vector2.ONE), Color("2f4c2a") if rng.randf() < 0.5 else Color("4a6e40"))
	tb.rect(r.grow(6.0), Color("6a6c78"))
	tb.rect(r, Color("44454f"))
	for i in 4000:
		var p := Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y))
		tb.rect(Rect2(p.floor(), Vector2.ONE), Color("3c3d46") if rng.randf() < 0.5 else Color("4e4f5a"))
	# Concrete slab seams.
	var x := r.position.x
	while x < r.end.x:
		tb.rect(Rect2(x, r.position.y, 1, r.size.y), Color("3a3b44"))
		x += 110.0
	var y := r.position.y
	while y < r.end.y:
		tb.rect(Rect2(r.position.x, y, r.size.x, 1), Color("3a3b44"))
		y += 95.0
	tb.flush(ci)


static func draw_markings(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var r := data.arena_rect
	var c := r.get_center()
	# Painted donut circles around the posts and the figure-eight guide.
	for p in data.posts:
		var pts := PackedVector2Array()
		for k in 41:
			var a := TAU * k / 40.0
			pts.append(p + Vector2(cos(a), sin(a)) * 60.0)
		for k in range(0, 40, 2):
			tb.line(pts[k], pts[k + 1], Color("f2c230"), 2.0)
	tb.line(data.posts[0], data.posts[1], Color(1, 1, 1, 0.25), 1.0)
	# Slalom guide line.
	for k in data.cones.size() - 1:
		tb.line(data.cones[k], data.cones[k + 1], Color(1, 1, 1, 0.2), 1.0)
	# Start boxes.
	for n in 2:
		var g := data.grid_slot(n)
		var gp: Vector2 = g["position"]
		tb.rect(Rect2(gp - Vector2(7, 10), Vector2(14, 20)), Color(1, 1, 1, 0.7), false, 1.0)
	tb.set_transform(c + Vector2(0, 120), 0.0)
	PixelText.draw(tb, Vector2(-PixelText.width_of("GYMKHANA", 3.0) * 0.5, -7), "GYMKHANA", Color(1, 1, 1, 0.35), 3.0, false)
	tb.reset_transform()
	t._draw_hazards(tb)
	tb.flush(ci)


static func draw_props(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var r := data.arena_rect
	# Tyre wall along the fence.
	var pts := [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y), r.position]
	for k in 4:
		var a: Vector2 = pts[k]
		var b: Vector2 = pts[k + 1]
		var n := int(a.distance_to(b) / 7.0)
		for i in n:
			var p := a.lerp(b, float(i) / n)
			tb.circle(p + Vector2(1, 1.5), 3.2, Color(0, 0, 0, 0.35))
			tb.circle(p, 3.2, Color("1c1c22") if i % 4 != 0 else Color("e8313f"))
			tb.circle(p + Vector2(-0.7, -0.7), 1.2, Color("4a4a56"))
	# Donut posts: stacks of tyres with a flag.
	for p in data.posts:
		tb.circle(p + Vector2(2, 3), 8.0, Color(0, 0, 0, 0.35))
		tb.circle(p, 8.0, Color("1c1c22"))
		tb.circle(p, 5.0, Color("ff7a1a"))
		tb.circle(p, 2.5, Color("1c1c22"))
	for p in data.cones:
		tb.circle(p + Vector2(1, 1.5), 3.0, Color(0, 0, 0, 0.3))
		tb.circle(p, 3.0, Color("ff7a1a"))
		tb.rect(Rect2(p - Vector2(0.5, 0.5), Vector2(1, 1)), Color.WHITE)
	t.spectators.draw_crowd(tb)
	tb.flush(ci)
