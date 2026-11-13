class_name Fields
extends RefCounted
## Open maps without a road: the stadium (car soccer, gate rush) and the
## sumo ring (a round platform above a glowing void, no walls at all).


static func build(t: Track) -> void:
	var data := t.data
	if data.field == "stadium":
		_stadium_walls(t)
		_crowd(t)
		t._add_layer("Ground", -10, func(ci: Node2D): Fields.draw_stadium(t, ci), true)
		t._add_layer("Scenery", 6, func(ci: Node2D): Fields.draw_stadium_top(t, ci))
	else:
		t._add_layer("Ground", -10, func(ci: Node2D): Fields.draw_sumo(t, ci), true)
		t._add_layer("Glow", 7, func(ci: Node2D): Fields.draw_sumo_glow(t, ci), false, true)


## Pitch walls with a gap for each goal, and the goal boxes behind them.
static func _stadium_walls(t: Track) -> void:
	var r := t.data.arena_rect
	var gh := t.data.goal_h * 0.5
	var cy := r.get_center().y
	var depth := 44.0
	var pts := [
		# top, right side down to the goal, the goal box, right side below...
		[r.position, Vector2(r.end.x, r.position.y)],
		[Vector2(r.end.x, r.position.y), Vector2(r.end.x, cy - gh)],
		[Vector2(r.end.x, cy - gh), Vector2(r.end.x + depth, cy - gh)],
		[Vector2(r.end.x + depth, cy - gh), Vector2(r.end.x + depth, cy + gh)],
		[Vector2(r.end.x + depth, cy + gh), Vector2(r.end.x, cy + gh)],
		[Vector2(r.end.x, cy + gh), r.end],
		[r.end, Vector2(r.position.x, r.end.y)],
		[Vector2(r.position.x, r.end.y), Vector2(r.position.x, cy + gh)],
		[Vector2(r.position.x, cy + gh), Vector2(r.position.x - depth, cy + gh)],
		[Vector2(r.position.x - depth, cy + gh), Vector2(r.position.x - depth, cy - gh)],
		[Vector2(r.position.x - depth, cy - gh), Vector2(r.position.x, cy - gh)],
		[Vector2(r.position.x, cy - gh), r.position],
	]
	var segs := PackedVector2Array()
	for s in pts:
		segs.append(s[0])
		segs.append(s[1])
	var body := StaticBody2D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	t.add_child(body)
	var shape := ConcavePolygonShape2D.new()
	shape.segments = segs
	var cs := CollisionShape2D.new()
	cs.shape = shape
	body.add_child(cs)


static func _crowd(t: Track) -> void:
	var r := t.data.arena_rect
	var shirts := [Color("e8313f"), Color("2f7ee8"), Color("f2c230"), Color("f4f4f4"), Color("2fae5a"), Color("ff5fb8")]
	var rng := RandomNumberGenerator.new()
	rng.seed = 41
	t.spectators.arena_mode = true
	var x := r.position.x + 6.0
	while x < r.end.x - 6.0:
		for row in 4:
			for side in [-1.0, 1.0]:
				if rng.randf() < 0.8:
					var y: float = r.position.y - 26.0 - row * 7.0 if side < 0.0 else r.end.y + 26.0 + row * 7.0
					# Left half wears blue, right half red: the two teams' fans.
					var col: Color = Color("3a7bff") if x < r.get_center().x and rng.randf() < 0.6 else (Color("ff3a4a") if rng.randf() < 0.6 else shirts[rng.randi_range(0, 5)])
					t.spectators.add_person(Vector2(x + rng.randf_range(-1.5, 1.5), y).round(), col, 0)
		x += 6.0


static func draw_stadium(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var r := data.arena_rect
	var c := r.get_center()
	tb.rect(data.bounds, Color("2a2a36"))
	# Stands.
	tb.rect(Rect2(r.position.x - 60, r.position.y - 60, r.size.x + 120, 50), Color("3b3b4c"))
	tb.rect(Rect2(r.position.x - 60, r.end.y + 10, r.size.x + 120, 50), Color("3b3b4c"))
	# Running track around the pitch.
	tb.rect(r.grow(10.0), Color("b5503c"))
	# Mown stripes.
	var stripe := r.size.x / 12.0
	for k in 12:
		tb.rect(Rect2(r.position.x + k * stripe, r.position.y, stripe, r.size.y), Color("3f8f3a") if k % 2 == 0 else Color("4a9c42"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	for i in 2500:
		var p := r.position + Vector2(rng.randf_range(0, r.size.x), rng.randf_range(0, r.size.y))
		tb.rect(Rect2(p.floor(), Vector2.ONE), Color("367d32") if rng.randf() < 0.5 else Color("58ad4e"))
	var line := Color(1, 1, 1, 0.85)
	tb.rect(r.grow(-6.0), line, false, 2.0)
	tb.line(Vector2(c.x, r.position.y + 6), Vector2(c.x, r.end.y - 6), line, 2.0)
	_ring(tb, c, 80.0, line)
	tb.circle(c, 4.0, line)
	# Penalty boxes.
	for side in [-1.0, 1.0]:
		var gx: float = r.position.x if side < 0.0 else r.end.x
		var w := 130.0
		var h := 300.0
		var box := Rect2(gx - (0.0 if side < 0.0 else w), c.y - h * 0.5, w, h)
		tb.rect(box, line, false, 2.0)
		tb.circle(Vector2(gx - side * 95.0, c.y), 3.0, line)
		# Goal box floor: blue on the left, red on the right.
		var gr := Rect2(gx if side > 0.0 else gx - 44.0, c.y - data.goal_h * 0.5, 44.0, data.goal_h)
		tb.rect(gr, Color("2f3550") if side < 0.0 else Color("502f35"))
		var col := Color("3a7bff") if side < 0.0 else Color("ff3a4a")
		tb.line(Vector2(gx, c.y - data.goal_h * 0.5), Vector2(gx, c.y + data.goal_h * 0.5), Color(col, 0.9), 3.0)
	tb.flush(ci)


static func draw_stadium_top(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var r := data.arena_rect
	var c := r.get_center()
	# Advertising boards on the walls.
	var ads := [Color("ff5fb8"), Color("3ee0ff"), Color("f2c230"), Color("7dff8a")]
	var x := r.position.x
	var k := 0
	while x < r.end.x:
		for y in [r.position.y - 8.0, r.end.y + 2.0]:
			tb.rect(Rect2(x, y, 62, 6), Color("1c1c26"))
			tb.rect(Rect2(x + 2, y + 1, 58, 4), ads[k % 4])
		x += 66.0
		k += 1
	# Goal frames and nets.
	for side in [-1.0, 1.0]:
		var gx: float = r.position.x if side < 0.0 else r.end.x
		var back: float = gx + side * 44.0
		var col := Color("3a7bff") if side < 0.0 else Color("ff3a4a")
		var top := c.y - data.goal_h * 0.5
		var bot := c.y + data.goal_h * 0.5
		var yy := top
		while yy <= bot:
			tb.line(Vector2(gx, yy), Vector2(back, yy), Color(1, 1, 1, 0.25), 1.0)
			yy += 8.0
		var xx := minf(gx, back)
		while xx <= maxf(gx, back):
			tb.line(Vector2(xx, top), Vector2(xx, bot), Color(1, 1, 1, 0.25), 1.0)
			xx += 8.0
		tb.line(Vector2(gx, top), Vector2(back, top), Color.WHITE, 3.0)
		tb.line(Vector2(gx, bot), Vector2(back, bot), Color.WHITE, 3.0)
		tb.line(Vector2(back, top), Vector2(back, bot), Color.WHITE, 3.0)
		tb.circle(Vector2(gx, top), 4.0, col)
		tb.circle(Vector2(gx, bot), 4.0, col)
	t.spectators.draw_crowd(tb)
	tb.flush(ci)


static func draw_sumo(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var c := data.arena_rect.get_center()
	var rr := data.ring_r
	# The void: dark with faint stars.
	tb.rect(data.bounds, Color("0b0a16"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 8
	for i in 500:
		var p := data.bounds.position + Vector2(rng.randf_range(0, data.bounds.size.x), rng.randf_range(0, data.bounds.size.y))
		tb.rect(Rect2(p.floor(), Vector2.ONE), Color(0.6, 0.55, 0.9, rng.randf_range(0.2, 0.7)))
	# Platform: drop shadow, side, top with sand texture and rings.
	tb.circle(c + Vector2(10, 16), rr + 4.0, Color(0, 0, 0, 0.5))
	tb.circle(c + Vector2(0, 8), rr, Color("5a3a28"))
	tb.circle(c, rr, Color("d9b77c"))
	for i in 3500:
		var a := rng.randf() * TAU
		var d := sqrt(rng.randf()) * (rr - 3.0)
		var p := c + Vector2(cos(a), sin(a)) * d
		tb.rect(Rect2(p.floor(), Vector2.ONE), Color("cfa96c") if rng.randf() < 0.5 else Color("e6c78f"))
	_ring(tb, c, rr - 10.0, Color("8a5a30"), 6.0)
	_ring(tb, c, rr - 2.0, Color("f7e2b0"), 2.0)
	_ring(tb, c, 70.0, Color(0.55, 0.36, 0.2, 0.6), 2.0)
	# Start lines.
	tb.line(c + Vector2(-30, -12), c + Vector2(-30, 12), Color("ffffff"), 3.0)
	tb.line(c + Vector2(30, -12), c + Vector2(30, 12), Color("ffffff"), 3.0)
	tb.flush(ci)


static func draw_sumo_glow(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var c := t.data.arena_rect.get_center()
	var rr := t.data.ring_r
	for k in 4:
		_ring(tb, c, rr + 6.0 + k * 5.0, Color(1.0, 0.35, 0.75, 0.16 - k * 0.035), 5.0)
	tb.flush(ci)


static func _ring(tb: TriBatch, c: Vector2, rad: float, col: Color, w := 2.0) -> void:
	var pts := PackedVector2Array()
	var n := maxi(24, int(rad / 4.0))
	for k in n + 1:
		var a := TAU * k / n
		pts.append(c + Vector2(cos(a), sin(a)) * rad)
	tb.polyline(pts, col, w)
