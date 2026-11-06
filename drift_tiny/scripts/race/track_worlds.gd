class_name TrackWorlds
extends RefCounted
## Drawing for the four "world" tracks (Desk Racers, Midnight Streets,
## Neon Vector, Golden Hour). Track calls these hooks; the generic road,
## barriers, drift zones and collision stay in Track.

const WORLDS := ["desk", "midnight", "vector", "autumn"]
const AUTUMN_PALETTES := [
	["7a2a18", "b4451e", "e0742a", "ffb04a"],
	["6a3a10", "a6621a", "dc9a26", "ffd45a"],
	["2f4a22", "44682c", "6a9238", "a6c25a"],
	["6a1e2a", "9e2f38", "d24a3e", "ff8a5a"],
]


static func is_world(theme: String) -> bool:
	return theme in WORLDS


# --- placement ----------------------------------------------------------------

## Scenery for a world track. Returns false for themes it does not handle.
static func place(t: Track) -> bool:
	match t.theme_name:
		"desk":
			t._scatter(["pencil", "mug", "eraser", "brick", "brick", "clip", "coin", "coin"], 170, 6.0, 260.0)
		"midnight":
			t._place_buildings()
			_place_parked(t)
			t._scatter(["planter", "planter", "cone"], 60, 4.0, 40.0)
		"vector":
			t._scatter(["hex", "hex", "cube"], 260, 6.0, 280.0)
		"autumn":
			_make_creek(t)
			t._scatter(["atree", "atree", "atree", "atree", "atree", "rock", "leafpile"], 560, 3.0, 260.0)
		_:
			return false
	return true


static func _place_parked(t: Track) -> void:
	var m := t.data.size()
	var wd := t._wall_dist()
	var i := 30
	while i < m:
		var side := 1.0 if (i / 50) % 2 == 0 else -1.0
		var p := t.data.samples[i] + t.data.normals[i] * side * (wd + 9.0)
		if t._clear(p, 5.0, i):
			t._decor.append({"type": "pcar", "pos": p, "r": 6.0, "seed": t._rng.randi(),
					"angle": t.data.tangents[i].angle()})
		i += 37


## A creek crossing the whole map top to bottom (it meets the road at least
## twice: those crossings become wooden bridges).
static func _make_creek(t: Track) -> void:
	var r := t.data.bounds
	var pts := PackedVector2Array()
	var x := r.get_center().x + t._rng.randf_range(-120, 120)
	var y := r.position.y - 40.0
	var raw := PackedVector2Array()
	while y < r.end.y + 80.0:
		raw.append(Vector2(x, y))
		x += t._rng.randf_range(-60, 60)
		y += 140.0
	for k in range(1, raw.size() - 2):
		for s in 12:
			pts.append(TrackData._catmull(raw[k - 1], raw[k], raw[k + 1], raw[k + 2], s / 12.0))
	t.creek = pts
	# Bridge centres: road samples the creek passes over.
	var hw := t.data.width * 0.5
	var m := t.data.size()
	var last := -999
	for i in range(0, m, 2):
		var p := t.data.samples[i]
		for c in pts:
			if p.distance_to(c) < 10.0:
				if absi(i - last) > 30:
					t.bridges.append(i)
					last = i
				break


# --- ground -------------------------------------------------------------------

static func ground(t: Track, tb: TriBatch, r: Rect2) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(t.data.id) + 11
	match t.theme_name:
		"desk":
			# Wooden planks with grain and knots.
			var y := floorf(r.position.y / 30.0) * 30.0
			while y < r.end.y:
				tb.rect(Rect2(r.position.x, y, r.size.x, 1), Color("8e5a33"))
				for k in 8:
					var gy := y + 3.0 + k * 3.0
					var x := r.position.x
					while x < r.end.x:
						var ln := rng.randf_range(18, 70)
						tb.rect(Rect2(x, gy, ln, 1), Color("a86c40") if rng.randf() < 0.6 else Color("c58856"))
						x += ln + rng.randf_range(6, 30)
				if rng.randf() < 0.7:
					var kx := rng.randf_range(r.position.x, r.end.x)
					tb.rect(Rect2(kx, y + 10, 8, 5), Color("8e5a33"), false, 1.0)
				y += 30.0
			# Notebook pages lying on the desk.
			for i in 7:
				var c := Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y))
				var a := rng.randf_range(-0.4, 0.4)
				tb.set_transform(c, a)
				tb.rect(Rect2(-58, -78, 120, 160), Color(0.2, 0.1, 0.05, 0.25))
				tb.rect(Rect2(-60, -80, 120, 160), Color("f6f1e4"))
				for ly in range(-70, 80, 7):
					tb.rect(Rect2(-60, ly, 120, 1), Color("b8d3ec"))
				tb.rect(Rect2(-46, -80, 1, 160), Color("eb8f8f"))
				tb.reset_transform()
		"midnight":
			# Pavement in square slabs.
			var c := Color("22222c")
			var x := r.position.x
			while x < r.end.x:
				tb.rect(Rect2(x, r.position.y, 1, r.size.y), c)
				x += 12.0
			var y := r.position.y
			while y < r.end.y:
				tb.rect(Rect2(r.position.x, y, r.size.x, 1), c)
				y += 12.0
		"vector":
			var g := Color("140f36")
			var x := floorf(r.position.x / 24.0) * 24.0
			while x < r.end.x:
				tb.rect(Rect2(x, r.position.y, 1, r.size.y), g)
				x += 24.0
			var y := floorf(r.position.y / 24.0) * 24.0
			while y < r.end.y:
				tb.rect(Rect2(r.position.x, y, r.size.x, 1), g)
				y += 24.0
		"autumn":
			if not t.creek.is_empty():
				_creek_draw(t, tb)
			for i in 2600:
				var p := Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y))
				tb.rect(Rect2(p.floor(), Vector2.ONE), Color(AUTUMN_PALETTES[rng.randi_range(0, 1)][rng.randi_range(2, 3)]))


static func _creek_draw(t: Track, tb: TriBatch) -> void:
	var pts := t.creek
	for i in pts.size() - 1:
		tb.line(pts[i], pts[i + 1], Color("c9b27a"), 30.0)
	for i in pts.size() - 1:
		tb.line(pts[i], pts[i + 1], Color("2f6f8a"), 22.0)
	for i in pts.size() - 1:
		tb.line(pts[i], pts[i + 1], Color("3f8aa6"), 13.0)
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	for i in range(0, pts.size() - 1, 2):
		var d := (pts[i + 1] - pts[i]).normalized()
		var n := Vector2(-d.y, d.x)
		var p := pts[i] + n * rng.randf_range(-7, 7)
		tb.line(p, p + d * 5.0, Color("9fd6e6"), 1.0)
		var s := pts[i] + n * (14.0 if rng.randf() < 0.5 else -14.0)
		tb.circle(s, rng.randf_range(1.0, 2.2), Color("9a8f86"))


## Sidewalks under the road edge (midnight) — drawn before the road.
static func under_road(t: Track, tb: TriBatch, hw: float) -> void:
	if t.theme_name != "midnight":
		return
	t._band(tb, -hw - 17.0, hw + 17.0, Color("3c3d4c"))
	t._band(tb, -hw - 5.0, hw + 5.0, Color("6a6c80"))
	var m := t.data.size()
	for i in range(0, m, 2):
		var j := (i + 1) % m
		t._quad(tb, i, j, hw + 10.0, hw + 11.0, Color("343544"))
		t._quad(tb, i, j, -hw - 11.0, -hw - 10.0, Color("343544"))


## Road surface extras: plastic track joints, fallen leaves, centre lines.
static func road_extra(t: Track, tb: TriBatch, hw: float) -> void:
	var m := t.data.size()
	match t.theme_name:
		"desk":
			t._band(tb, -hw, -hw + 4.0, Color("d85f0c"))
			t._band(tb, hw - 4.0, hw, Color("d85f0c"))
			for i in m:
				if fmod(t.data.cum_len[i], 30.0) < TrackData.SPACING:
					t._quad(tb, i, (i + 1) % m, -hw, hw, Color("c9560a"))
		"autumn":
			var rng := RandomNumberGenerator.new()
			rng.seed = 77
			for k in 900:
				var i := rng.randi_range(0, m - 1)
				var p := t.data.samples[i] + t.data.normals[i] * rng.randf_range(-hw, hw)
				tb.rect(Rect2(p.floor(), Vector2.ONE), Color(AUTUMN_PALETTES[rng.randi_range(0, 3)][rng.randi_range(1, 3)]))


static func markings_extra(t: Track, tb: TriBatch, hw: float) -> void:
	var m := t.data.size()
	match t.theme_name:
		"midnight":
			# Double yellow centre line and zebra crossings every few blocks.
			for i in m:
				var j := (i + 1) % m
				t._quad(tb, i, j, -2.0, -1.0, Color("d8b23a"))
				t._quad(tb, i, j, 1.0, 2.0, Color("d8b23a"))
			var i := 60
			while i < m:
				for s in range(i, i + 3):
					for k in range(-int(hw) + 4, int(hw) - 4, 8):
						t._quad(tb, s % m, (s + 1) % m, k, k + 5, Color("c9cad6"))
				i += 140
		"vector":
			t._band(tb, -hw, -hw + 1.0, Color("ff2aa8"))
			t._band(tb, hw - 1.0, hw, Color("2ae0ff"))
		"autumn":
			for b in t.bridges:
				_bridge(t, tb, int(b), hw)


static func _bridge(t: Track, tb: TriBatch, c: int, hw: float) -> void:
	var m := t.data.size()
	for k in range(c - 6, c + 7):
		var i := posmod(k, m)
		var j := posmod(k + 1, m)
		t._quad(tb, i, j, -hw - 8.0, hw + 8.0, Color("a0703c") if k % 2 == 0 else Color("8a5e30"))
	for side in [-1.0, 1.0]:
		for k in range(c - 7, c + 7):
			var i := posmod(k, m)
			var j := posmod(k + 1, m)
			t._quad(tb, i, j, side * (hw + 8.0), side * (hw + 10.0), Color("5a3a1c"))


# --- barriers -------------------------------------------------------------

## Barrier styles of the worlds. Returns false if the style is not one of them.
static func barrier(tb: TriBatch, style: String, pts: PackedVector2Array, lines: PackedVector2Array) -> bool:
	var n := pts.size()
	match style:
		"ruler":
			# A yellow school ruler with tick marks.
			tb.multiline(lines, Color("8a6a10"), 4.0)
			tb.multiline(lines, Color("f2c430"), 2.5)
			for i in range(0, n, 2):
				tb.rect(Rect2(pts[i] - Vector2(0.5, 0.5), Vector2(1, 1)), Color("3a2a08"))
			return true
		"laser":
			tb.multiline(lines, Color("ff2aa8"), 1.0)
			return true
	return false


# --- scenery ------------------------------------------------------------------

## Draws one decor item of a world. Returns false for unknown types.
static func decor(t: Track, tb: TriBatch, d: Dictionary) -> bool:
	var p: Vector2 = d["pos"]
	var r: float = d["r"]
	var rng := RandomNumberGenerator.new()
	rng.seed = d["seed"]
	var outline := Color("2b1a0c")
	match d["type"]:
		"pencil":
			var cols := [Color("f4c430"), Color("e8313f"), Color("2f7ee8"), Color("2fae5a")]
			var body: Color = cols[rng.randi_range(0, 3)]
			var ang := rng.randf() * PI
			tb.set_transform(p + Vector2(4, 4), ang)
			tb.rect(Rect2(-40, -4, 80, 8), Color(0.2, 0.1, 0.05, 0.3))
			tb.set_transform(p, ang)
			tb.rect(Rect2(-41, -5, 82, 10), outline)
			tb.rect(Rect2(-40, -4, 64, 8), body)
			tb.rect(Rect2(-40, -1, 64, 2), body.darkened(0.2))
			tb.polygon(PackedVector2Array([Vector2(24, -4), Vector2(40, 0), Vector2(24, 4)]), Color("eecb98"))
			tb.polygon(PackedVector2Array([Vector2(35, -1.5), Vector2(40, 0), Vector2(35, 1.5)]), Color("333333"))
			tb.rect(Rect2(-46, -4, 6, 8), Color("c0c3c8"))
			tb.rect(Rect2(-52, -4, 6, 8), Color("ff8fa8"))
			tb.reset_transform()
		"mug":
			tb.circle(p + Vector2(4, 5), 20.0, Color(0.2, 0.1, 0.05, 0.3))
			tb.circle(p, 20.0, outline)
			tb.circle(p, 19.0, Color("e8ecf2"))
			tb.circle(p, 15.0, Color("6b3d1c"))
			tb.circle(p + Vector2(-5, -5), 5.0, Color("8b5530"))
			tb.rect(Rect2(p + Vector2(18, -5), Vector2(8, 10)), outline)
			tb.rect(Rect2(p + Vector2(19, -4), Vector2(6, 8)), Color("e8ecf2"))
		"eraser":
			tb.set_transform(p, rng.randf() * PI)
			tb.rect(Rect2(-12, -6, 26, 14), Color(0.2, 0.1, 0.05, 0.3))
			tb.rect(Rect2(-14, -8, 28, 15), outline)
			tb.rect(Rect2(-13, -7, 26, 13), Color("ff9db2"))
			tb.rect(Rect2(-13, -7, 9, 13), Color("4a8af5"))
			tb.reset_transform()
		"brick":
			var cols := [Color("2f6fe0"), Color("e8313f"), Color("f2c230"), Color("2fae5a")]
			var c: Color = cols[rng.randi_range(0, 3)]
			tb.set_transform(p, float(rng.randi_range(0, 3)) * PI * 0.5)
			tb.rect(Rect2(-14, -8, 32, 20), Color(0.2, 0.1, 0.05, 0.3))
			tb.rect(Rect2(-17, -11, 34, 22), outline)
			tb.rect(Rect2(-16, -10, 32, 20), c)
			for bx in [-10.0, -2.0, 6.0, 14.0]:
				for by in [-5.0, 4.0]:
					tb.circle(Vector2(bx - 2, by), 2.6, c.darkened(0.25))
					tb.circle(Vector2(bx - 2, by - 0.8), 2.4, c.lightened(0.2))
			tb.reset_transform()
		"clip":
			tb.set_transform(p, rng.randf() * PI)
			tb.rect(Rect2(-14, -5, 28, 10), Color("9aa4b4"), false, 1.0)
			tb.rect(Rect2(-10, -3, 20, 6), Color("c8d0dc"), false, 1.0)
			tb.reset_transform()
		"coin":
			tb.circle(p + Vector2(1, 2), 6.0, Color(0.2, 0.1, 0.05, 0.3))
			tb.circle(p, 6.0, Color("a07a20"))
			tb.circle(p, 5.0, Color("e8c040"))
			tb.circle(p + Vector2(-1.5, -1.5), 1.5, Color("fff0a0"))
		"planter":
			tb.rect(Rect2(p - Vector2(6, 6), Vector2(12, 12)), Color("5a5a68"))
			tb.rect(Rect2(p - Vector2(5, 5), Vector2(10, 10)), Color("3a2a20"))
			tb.circle(p + Vector2(2, 3), 6.0, Color(0, 0, 0, 0.35))
			tb.circle(p, 6.0, Color("1f3a2a"))
			tb.circle(p + Vector2(-1.5, -1.5), 3.0, Color("2f5a3a"))
		"cone":
			tb.circle(p, 2.5, Color("ff7a1a"))
			tb.rect(Rect2(p - Vector2(0.5, 0.5), Vector2(1, 1)), Color.WHITE)
		"pcar":
			var cols := [Color("6a7486"), Color("8a3a3a"), Color("3a5a8a"), Color("c8c8d0"), Color("2a2a30")]
			var c: Color = cols[rng.randi_range(0, cols.size() - 1)]
			tb.set_transform(p + Vector2(1.5, 2), float(d["angle"]))
			tb.rect(Rect2(-7, -4, 14, 8), Color(0, 0, 0, 0.35))
			tb.set_transform(p, float(d["angle"]))
			tb.rect(Rect2(-7, -4, 14, 8), c.darkened(0.35))
			tb.rect(Rect2(-6.5, -3.5, 13, 7), c)
			tb.rect(Rect2(-2, -3, 5, 6), c.darkened(0.12))
			tb.rect(Rect2(3, -3, 1.5, 6), Color("223040"))
			tb.rect(Rect2(-3.5, -3, 1.5, 6), Color("223040"))
			tb.reset_transform()
		"hex":
			var col: Color = [Color("3cff8c"), Color("2ae0ff"), Color("a95cff")][rng.randi_range(0, 2)]
			var pts := PackedVector2Array()
			for k in 7:
				var a := TAU * k / 6.0
				pts.append(p + Vector2(cos(a), sin(a)) * r)
			tb.polyline(pts, col, 1.0)
			tb.rect(Rect2(p - Vector2(0.5, 0.5), Vector2(1, 1)), col)
		"cube":
			var col := Color("ffd84a")
			var s := r * 0.8
			tb.rect(Rect2(p - Vector2(s, s), Vector2(s * 2, s * 2)), col, false, 1.0)
			tb.rect(Rect2(p - Vector2(s, s) + Vector2(3, -3), Vector2(s * 2, s * 2)), Color(col, 0.5), false, 1.0)
		"atree":
			var pal: Array = AUTUMN_PALETTES[rng.randi_range(0, 3)]
			# Long low-sun shadow first.
			for k in range(0, 22, 2):
				tb.circle(p + Vector2(k, k * 0.55), r * 0.75, Color(0.12, 0.08, 0.24, 0.1))
			tb.circle(p, r, Color(pal[0]))
			for k in 8:
				var a := rng.randf_range(0, TAU)
				var o := Vector2(cos(a), sin(a)) * r * 0.4
				tb.circle(p + o, r * rng.randf_range(0.35, 0.55), Color(pal[1]))
			for k in 5:
				var o := Vector2(rng.randf_range(-r * 0.6, r * 0.1), rng.randf_range(-r * 0.6, r * 0.1))
				tb.circle(p + o, r * rng.randf_range(0.2, 0.32), Color(pal[2]))
			for k in 4:
				tb.rect(Rect2((p + Vector2(-r * 0.4 + rng.randf_range(-3, 3), -r * 0.45 + rng.randf_range(-3, 3))).floor(), Vector2.ONE), Color(pal[3]))
		"leafpile":
			for k in 10:
				var o := Vector2(rng.randf_range(-r, r), rng.randf_range(-r * 0.6, r * 0.6))
				tb.rect(Rect2((p + o).floor(), Vector2(2, 1)), Color(AUTUMN_PALETTES[rng.randi_range(0, 3)][rng.randi_range(1, 3)]))
		_:
			return false
	return true


## Midnight Streets: dark rooftops with lit windows, vents and a small sign.
static func city_building(tb: TriBatch, b: Dictionary) -> void:
	var rect: Rect2 = b["rect"]
	var rng := RandomNumberGenerator.new()
	rng.seed = b["seed"]
	tb.rect(Rect2(rect.position + Vector2(5, 6), rect.size), Color(0, 0, 0, 0.5))
	tb.rect(rect, Color("12101c"))
	tb.rect(rect.grow(-1.0), Color("26222f").lerp(Color("1d2b33"), rng.randf()))
	for i in rng.randi_range(3, 7):
		var s := Vector2(rng.randi_range(4, 10), rng.randi_range(3, 8))
		var p := (rect.position + Vector2(rng.randf_range(3, rect.size.x - s.x - 3), rng.randf_range(3, rect.size.y - s.y - 3))).round()
		tb.rect(Rect2(p + Vector2(1, 1), s), Color(0, 0, 0, 0.4))
		tb.rect(Rect2(p, s), Color("4a4866"))
		tb.rect(Rect2(p, Vector2(s.x, 1)), Color("6a6890"))
	# Skylights / lit windows along the edges.
	var x := rect.position.x + 4.0
	while x < rect.end.x - 6.0:
		if rng.randf() < 0.45:
			tb.rect(Rect2(x, rect.end.y - 5.0, 4, 2), Color("ffe8a0") if rng.randf() < 0.6 else Color("a0d8ff"))
		x += 7.0
	if rng.randf() < 0.45:
		var neon: Color = b["neon"]
		var word: String = b["word"]
		tb.rect(Rect2(rect.position + Vector2(3, 3), Vector2(PixelText.width_of(word) + 6, 9)), Color("0a0812"))
		PixelText.draw(tb, rect.position + Vector2(6, 5), word, neon, 1.0, false)


## Additive glow of the vector world: road edges and shapes.
static func vector_glow(t: Track, tb: TriBatch) -> void:
	var hw := t.data.width * 0.5
	var m := t.data.size()
	for i in m:
		var j := (i + 1) % m
		t._quad(tb, i, j, -hw - 2.0, -hw + 3.0, Color(1.0, 0.16, 0.66, 0.22))
		t._quad(tb, i, j, hw - 3.0, hw + 2.0, Color(0.16, 0.88, 1.0, 0.22))
	for side_pts in [t.wall_left, t.wall_right]:
		var pts: PackedVector2Array = side_pts
		for i in pts.size() - 1:
			if pts[i].distance_to(pts[i + 1]) < 24.0:
				tb.line(pts[i], pts[i + 1], Color(1.0, 0.16, 0.66, 0.25), 4.0)
