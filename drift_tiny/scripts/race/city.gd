class_name City
extends RefCounted
## Downtown: the open city for the police chase and hot potato. Streets with
## lane markings and crosswalks, sidewalks, buildings with rooftops, parks
## with trees, cash bags lying on the streets.


static func build(t: Track) -> void:
	var data := t.data
	var r := data.arena_rect
	var body := StaticBody2D.new()
	body.collision_layer = 1
	body.collision_mask = 0
	t.add_child(body)
	# Outer wall.
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
	for b in data.blocks:
		var br := b as Rect2
		var shape := RectangleShape2D.new()
		shape.size = br.size
		var bc := CollisionShape2D.new()
		bc.shape = shape
		bc.position = br.get_center()
		body.add_child(bc)
	for p in data.trees:
		var ts := CircleShape2D.new()
		ts.radius = 7.0
		var tc := CollisionShape2D.new()
		tc.shape = ts
		tc.position = p
		body.add_child(tc)
	t._add_layer("Ground", -10, func(ci: Node2D): City.draw_ground(t, ci), true)
	t._add_layer("Markings", -7, func(ci: Node2D): City.draw_markings(t, ci))
	t._add_layer("Buildings", 6, func(ci: Node2D): City.draw_buildings(t, ci))


static func draw_ground(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var r := data.arena_rect
	tb.rect(data.bounds, Color("23232b"))
	tb.rect(r, Color("3b3c46"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	for i in 9000:
		var p := Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y))
		tb.rect(Rect2(p.floor(), Vector2.ONE), Color("35363f") if rng.randf() < 0.5 else Color("44454f"))
	# Patched asphalt.
	for i in 40:
		var p := Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y))
		tb.rect(Rect2(p.floor(), Vector2(rng.randi_range(12, 40), rng.randi_range(8, 20))), Color("383943"))
	# Sidewalks around every block (also around parks).
	for b in data.blocks + data.parks:
		var br := b as Rect2
		tb.rect(br.grow(9.0), Color("8d8d99"))
		tb.rect(br.grow(9.0), Color("6d6d78"), false, 1.0)
		# Paving joints.
		var x := br.position.x - 9.0
		while x < br.end.x + 9.0:
			tb.rect(Rect2(x, br.position.y - 9.0, 1, 9), Color("7c7c88"))
			tb.rect(Rect2(x, br.end.y, 1, 9), Color("7c7c88"))
			x += 12.0
		var y := br.position.y - 9.0
		while y < br.end.y + 9.0:
			tb.rect(Rect2(br.position.x - 9.0, y, 9, 1), Color("7c7c88"))
			tb.rect(Rect2(br.end.x, y, 9, 1), Color("7c7c88"))
			y += 12.0
	for b in data.parks:
		var br := b as Rect2
		tb.rect(br, Color("3f7a3a"))
		for i in 500:
			var p := br.position + Vector2(rng.randf_range(0, br.size.x), rng.randf_range(0, br.size.y))
			tb.rect(Rect2(p.floor(), Vector2.ONE), Color("4a8a43") if rng.randf() < 0.5 else Color("356a31"))
		# Footpaths crossing the park.
		var c := br.get_center()
		tb.rect(Rect2(br.position.x, c.y - 6, br.size.x, 12), Color("b9a17a"))
		tb.rect(Rect2(c.x - 6, br.position.y, 12, br.size.y), Color("b9a17a"))
		tb.circle(c, 26.0, Color("b9a17a"))
		tb.circle(c, 14.0, Color("5aa6d8"))
		tb.circle(c, 10.0, Color("7cc4ee"))
	tb.flush(ci)


static func draw_markings(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var half := TrackData.STREET * 0.5
	# Dashed yellow centre lines between intersections, white stop lines and
	# zebra crossings at every junction.
	for n in data.nodes.size():
		for m in data.links[n]:
			if int(m) < n:
				continue
			var a := data.nodes[n]
			var b := data.nodes[int(m)]
			var dir := (b - a).normalized()
			var from := a + dir * (half + 14.0)
			var to := b - dir * (half + 14.0)
			var seg_len := from.distance_to(to)
			var d := 0.0
			while d < seg_len:
				tb.line(from + dir * d, from + dir * minf(d + 14.0, seg_len), Color("e8c23a"), 2.0)
				d += 26.0
			var perp := Vector2(-dir.y, dir.x)
			for end in [[from, 1.0], [to, -1.0]]:
				var e: Vector2 = end[0]
				var s: float = end[1]
				for k in range(-4, 5):
					var p := e - dir * s * 7.0 + perp * k * 9.5
					tb.line(p - dir * s * 5.0, p + dir * s * 3.0, Color(1, 1, 1, 0.55), 4.0)
	# Manholes and drains.
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	for n in data.nodes.size():
		if rng.randf() < 0.5:
			var p := data.nodes[n] + Vector2(rng.randf_range(-20, 20), rng.randf_range(-20, 20))
			tb.circle(p, 5.0, Color("2c2d35"))
			tb.circle(p, 4.0, Color("4a4b55"))
	t._draw_hazards(tb)
	tb.flush(ci)


static func draw_buildings(t: Track, ci: Node2D) -> void:
	var tb := TriBatch.new()
	var data := t.data
	var rng := RandomNumberGenerator.new()
	rng.seed = 23
	var roofs := [Color("5b6170"), Color("7a5a52"), Color("54606e"), Color("8a7b6a"), Color("4f5664"),
			Color("6e5e7c"), Color("5f7068"), Color("8b6b5a")]
	for b in data.blocks:
		var br := b as Rect2
		# Split the block into 2-4 buildings of different heights.
		var parts: Array = []
		if rng.randf() < 0.5:
			var cut := rng.randf_range(0.35, 0.65) * br.size.x
			parts = [Rect2(br.position, Vector2(cut, br.size.y)), Rect2(br.position + Vector2(cut, 0), Vector2(br.size.x - cut, br.size.y))]
		else:
			var cx := rng.randf_range(0.4, 0.6) * br.size.x
			var cy := rng.randf_range(0.4, 0.6) * br.size.y
			parts = [Rect2(br.position, Vector2(cx, cy)), Rect2(br.position + Vector2(cx, 0), Vector2(br.size.x - cx, cy)),
					Rect2(br.position + Vector2(0, cy), Vector2(cx, br.size.y - cy)), Rect2(br.position + Vector2(cx, cy), br.size - Vector2(cx, cy))]
		for p in parts:
			var pr := (p as Rect2).grow(-2.0)
			var hgt := rng.randf_range(4.0, 12.0)
			# Shadow to the lower right, taller buildings throw longer ones.
			tb.rect(Rect2(pr.position + Vector2(hgt, hgt * 1.2), pr.size), Color(0, 0, 0, 0.28))
			var roof: Color = roofs[rng.randi_range(0, roofs.size() - 1)]
			tb.rect(pr, roof.darkened(0.35))
			var top := Rect2(pr.position, pr.size - Vector2(0, 4))
			tb.rect(top, roof)
			tb.rect(Rect2(top.position, Vector2(top.size.x, 2)), roof.lightened(0.18))
			tb.rect(Rect2(top.position, Vector2(2, top.size.y)), roof.lightened(0.1))
			tb.rect(top.grow(-6.0), roof.darkened(0.08), false, 1.0)
			# Rooftop details: AC units, vents, a water tank or a helipad.
			var kind := rng.randi_range(0, 3)
			var inner := top.grow(-12.0)
			if inner.size.x < 20.0 or inner.size.y < 20.0:
				continue
			for k in rng.randi_range(2, 5):
				var q := inner.position + Vector2(rng.randf_range(0, inner.size.x - 14), rng.randf_range(0, inner.size.y - 10))
				tb.rect(Rect2(q + Vector2(2, 2), Vector2(14, 10)), Color(0, 0, 0, 0.3))
				tb.rect(Rect2(q, Vector2(14, 10)), Color("b8bcc6"))
				tb.circle(q + Vector2(7, 5), 3.5, Color("7d828e"))
			match kind:
				0:
					var c := inner.get_center()
					tb.circle(c + Vector2(3, 3), 11.0, Color(0, 0, 0, 0.3))
					tb.circle(c, 11.0, Color("6a4e3a"))
					tb.circle(c, 8.0, Color("7d5d45"))
				1:
					var c := inner.get_center()
					if inner.size.x > 50.0 and inner.size.y > 50.0:
						tb.circle(c, 20.0, Color("3d4350"))
						tb.circle(c, 18.0, Color("4a5160"))
						PixelText.draw_centered(tb, c - Vector2(0, 3), "H", Color("f2c230"), 2.0)
				2:
					# Glass skylight strip.
					tb.rect(Rect2(inner.position.x, inner.get_center().y - 4, inner.size.x, 8), Color("7fb2d6"))
					tb.rect(Rect2(inner.position.x, inner.get_center().y - 4, inner.size.x, 2), Color("b8dcf2"))
				_:
					pass
	# Park trees.
	for p in data.trees:
		var tp: Vector2 = p
		tb.circle(tp + Vector2(4, 5), 12.0, Color(0, 0, 0, 0.3))
		tb.circle(tp, 12.0, Color("2f6a2c"))
		tb.circle(tp + Vector2(-3, -3), 8.0, Color("3f8a3a"))
		tb.circle(tp + Vector2(-5, -5), 3.0, Color("5aa850"))
	# Street lamps at the corners of every junction.
	var off := TrackData.STREET * 0.5 + 5.0
	for n in data.nodes.size():
		for s in [Vector2(-1, -1), Vector2(1, 1)]:
			var lp := data.nodes[n] + (s as Vector2) * off
			if not data.arena_rect.has_point(lp):
				continue
			tb.circle(lp + Vector2(1, 2), 2.5, Color(0, 0, 0, 0.35))
			tb.circle(lp, 2.5, Color("2a2a32"))
			tb.circle(lp, 1.3, Color("ffe7a0"))
	tb.flush(ci)
