class_name Track
extends Node2D
## Builds a playable track from TrackData: ground, road surface, curbs,
## markings, barriers (with collision) and themed scenery. All of it is drawn
## procedurally once; Godot caches the draw commands, so it costs nothing per
## frame. The camera always looks straight down — depth comes from shadows and
## layering only.

const THEMES := {
	"mountain": {
		"ground": "3d6a48", "ground_dark": "32583c", "ground_light": "558a58",
		"road": "4b4757", "road_dark": "3f3b4b", "road_light": "5a5568", "shoulder": "6b5a4a",
		"line": "e9e4ea", "curb_a": "d94056", "curb_b": "efe9ee",
		"wall": "c9cdd8", "wall_dark": "6c7080", "wall_style": "rail",
		"tree": "275a3a", "tree_dark": "1d4430", "tree_light": "3f7a4e",
		"accent": "f7a6cf", "accent_dark": "d877aa", "rock": "7a7480",
		"lamp": "ffd27a", "dashes": true,
	},
	"neon": {
		"ground": "1d1a33", "ground_dark": "17142b", "ground_light": "29254a",
		"road": "25233b", "road_dark": "1e1c31", "road_light": "34315a", "shoulder": "3a3756",
		"line": "b9b4e0", "curb_a": "ff3da5", "curb_b": "302d4c",
		"wall": "5a5880", "wall_dark": "2a2840", "wall_style": "concrete",
		"tree": "1f3a3a", "tree_dark": "142828", "tree_light": "2c5050",
		"accent": "ff3da5", "accent_dark": "3ee0ff", "rock": "403c5c",
		"lamp": "ffe6a0", "dashes": true,
	},
	"forest": {
		"ground": "355c2a", "ground_dark": "2a4a22", "ground_light": "4d7a36",
		"road": "8a6a46", "road_dark": "76583a", "road_light": "9c7c56", "shoulder": "5e4a30",
		"line": "000000", "curb_a": "d94056", "curb_b": "efe9ee",
		"wall": "8a5c36", "wall_dark": "4e3420", "wall_style": "fence",
		"tree": "1e4a2c", "tree_dark": "163a22", "tree_light": "2f6a3c",
		"accent": "e8c84a", "accent_dark": "a8842a", "rock": "6e6e72",
		"lamp": "ffd27a", "dashes": false,
	},
	"snow": {
		"ground": "dfe8f2", "ground_dark": "c4d2e4", "ground_light": "f6f9fd",
		"road": "8f9bb0", "road_dark": "7d889e", "road_light": "a9b4c6", "shoulder": "c0cada",
		"line": "eef2f8", "curb_a": "3e6fd8", "curb_b": "f0f4fa",
		"wall": "aab4c6", "wall_dark": "5c6478", "wall_style": "rail",
		"tree": "2a4e48", "tree_dark": "1d3a36", "tree_light": "f0f6ff",
		"accent": "bfe6ff", "accent_dark": "8fc4e8", "rock": "6e7488",
		"lamp": "ffe0a0", "dashes": true,
	},
}

const NEON_WORDS := ["DRIFT", "TINY", "CAFE", "24H", "NEON", "HOTEL", "RAMEN", "ARCADE", "BAR", "GAS"]

var data: TrackData
var pal: Dictionary = {}
var theme_name := "mountain"
var night := false
var wall_left := PackedVector2Array()
var wall_right := PackedVector2Array()

var _rng := RandomNumberGenerator.new()
var _decor: Array = []      # {type, pos, size, color...}
var _buildings: Array = []
var _lamps: Array = []
var _chevrons: Array = []
var _shore := INF
var toy := false             # "Toy Racer" style: banners, tyre walls, more curbs
var _banners: Array = []


func build(track_data: TrackData) -> void:
	data = track_data
	theme_name = data.theme
	night = theme_name == "neon" or GraphicsStyle.flag("night")
	toy = GraphicsStyle.flag("toy")
	pal = {}
	var raw: Dictionary = THEMES.get(theme_name, THEMES["mountain"])
	if GraphicsStyle.flag("toy"):
		# Toy box palette: sandy track, bright lawn, white lines.
		raw = raw.duplicate()
		raw.merge({"ground": "4fae4a", "ground_dark": "449a40", "ground_light": "62c25a",
				"road": "c89664", "road_dark": "b4844f", "road_light": "d8a876", "shoulder": "8e6a44",
				"line": "f4f4f4", "dashes": true}, true)
	for k in raw.keys():
		# Everything except the few non-colour settings is a hex colour.
		var is_color: bool = typeof(raw[k]) == TYPE_STRING and k != "wall_style"
		pal[k] = Color.html(raw[k]) if is_color else raw[k]
	_rng.seed = hash(data.id)
	_shore = _compute_shore_y()
	wall_left = data.wall_points(-1.0)
	wall_right = data.wall_points(1.0)
	_build_walls()
	_place_scenery()
	_add_layer("Ground", -10, _draw_ground, true)
	_add_layer("Road", -8, _draw_road)
	_add_layer("Markings", -7, _draw_markings)
	_add_layer("Barriers", 3, _draw_barriers)
	_add_layer("Scenery", 6, _draw_scenery)
	if night and Game.quality() > 0:
		_add_layer("Glow", 7, _draw_glow, false, true)
	if theme_name == "mountain" and GraphicsStyle.flag("sunset_tint"):
		# Warm sunset light over the whole world.
		var tint := CanvasModulate.new()
		tint.color = Color(1.0, 0.84, 0.9)
		add_child(tint)
	elif night and theme_name != "neon":
		# Night falls over a daytime track.
		var dark := CanvasModulate.new()
		dark.color = Color(0.42, 0.45, 0.66)
		add_child(dark)


func _add_layer(layer_name: String, z: int, painter: Callable, repeat := false, additive := false) -> Node2D:
	var n := Node2D.new()
	n.name = layer_name
	n.z_index = z
	if repeat:
		n.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	if additive:
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		n.material = mat
	add_child(n)
	n.draw.connect(painter.bind(n))
	n.queue_redraw()
	return n


func color(key: String) -> Color:
	return pal.get(key, Color.MAGENTA)


# --- collision ------------------------------------------------------------

func _build_walls() -> void:
	var body := StaticBody2D.new()
	body.name = "Barriers"
	body.collision_layer = 1
	body.collision_mask = 0
	add_child(body)
	for pts in [wall_left, wall_right]:
		var segs := _segments(pts)
		if segs.is_empty():
			continue
		var shape := ConcavePolygonShape2D.new()
		shape.segments = segs
		var cs := CollisionShape2D.new()
		cs.shape = shape
		body.add_child(cs)


## Segment pairs along a wall polyline; gaps left by folded corners stay open.
func _segments(pts: PackedVector2Array) -> PackedVector2Array:
	var segs := PackedVector2Array()
	var n := pts.size()
	for i in n:
		var a := pts[i]
		var b := pts[(i + 1) % n]
		if a.distance_to(b) > 24.0:
			continue
		segs.append(a)
		segs.append(b)
	return segs


# --- strip helpers (into a TriBatch) -------------------------------------------------------------

## Fills the band between two offsets from the centre line (closed loop).
## Plain triangles, so folded inner corners never break triangulation.
func _band(tb: TriBatch, off_a: float, off_b: float, col: Color, from_i := 0, to_i := -1) -> void:
	var m := data.size()
	if to_i < 0:
		to_i = m
	var s := data.samples
	var nr := data.normals
	for k in range(from_i, to_i):
		var i := posmod(k, m)
		var j := posmod(k + 1, m)
		tb.quad(s[i] + nr[i] * off_a, s[j] + nr[j] * off_a, s[j] + nr[j] * off_b, s[i] + nr[i] * off_b, col)


func _quad(tb: TriBatch, i: int, j: int, off_a: float, off_b: float, col: Color) -> void:
	var s := data.samples
	var n := data.normals
	tb.quad(s[i] + n[i] * off_a, s[j] + n[j] * off_a, s[j] + n[j] * off_b, s[i] + n[i] * off_b, col)


# --- painters -------------------------------------------------------------

func _draw_ground(ci: Node2D) -> void:
	var tb := TriBatch.new()
	var tex := FxTextures.ground(theme_name, color("ground"), color("ground_dark"), color("ground_light"), hash(theme_name))
	var r := data.bounds
	ci.draw_texture_rect(tex, r, true)
	if toy:
		# Mowed-lawn checkerboard.
		var cell := 24.0
		var y := floorf(r.position.y / cell) * cell
		while y < r.end.y:
			var x := floorf(r.position.x / cell) * cell
			while x < r.end.x:
				if int(x / cell + y / cell) % 2 == 0:
					tb.rect(Rect2(x, y, cell, cell), Color(1, 1, 1, 0.07))
				x += cell
			y += cell
	if theme_name == "mountain":
		_draw_sea(tb, r)
	elif theme_name == "neon":
		_draw_city_blocks(tb, r)
	tb.flush(ci)


func _draw_sea(tb: TriBatch, r: Rect2) -> void:
	# The sea lies south of the track, beyond a rocky cliff edge.
	var shore := _shore
	var sea := Rect2(r.position.x, shore, r.size.x, r.end.y - shore + 400.0)
	tb.rect(sea, Color("2c3f86"))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	# Sunset reflection: warm streaks under the sun's position.
	var sun_x := r.get_center().x + 300.0
	for i in 70:
		var y := shore + 14.0 + i * 5.0
		var w := 40.0 + rng.randf() * 120.0 * (1.0 - i / 90.0)
		var c := Color("ff9a5a").lerp(Color("c05a8a"), i / 70.0)
		tb.rect(Rect2(sun_x - w * 0.5 + rng.randf_range(-20, 20), y, w, 1.0), c)
	for i in 260:
		var x := r.position.x + rng.randf() * r.size.x
		var y := shore + 10.0 + rng.randf() * (sea.size.y - 10.0)
		tb.rect(Rect2(x, y, rng.randf_range(3, 10), 1.0), Color("4a64b0"))
	# Cliff: jagged band of rock between grass and water (drawn as columns,
	# so no polygon triangulation is involved).
	var x0 := r.position.x
	var x := x0
	while x < r.end.x:
		var w := rng.randf_range(6, 14)
		var top := shore - 24.0 + rng.randf_range(-8, 8)
		var bottom := shore + rng.randf_range(2, 10)
		tb.rect(Rect2(x, top, w + 1.0, bottom - top), Color("6b5f70"))
		x += w
	for i in 120:
		var px := x0 + rng.randf() * r.size.x
		tb.rect(Rect2(px, shore - 18.0 + rng.randf() * 22.0, 3, 2), Color("8a7e8e") if i % 2 == 0 else Color("4e4456"))
	for i in 160:
		var px := x0 + rng.randf() * r.size.x
		tb.rect(Rect2(px, shore + 6.0 + rng.randf() * 4.0, rng.randf_range(2, 6), 1.0), Color(1, 1, 1, 0.6))


func _draw_city_blocks(tb: TriBatch, _r: Rect2) -> void:
	# Pavement grid lines on the ground read as city blocks from above.
	var r := data.bounds
	var c := Color("221f3c")
	var x := r.position.x
	while x < r.end.x:
		tb.rect(Rect2(x, r.position.y, 1, r.size.y), c)
		x += 32.0
	var y := r.position.y
	while y < r.end.y:
		tb.rect(Rect2(r.position.x, y, r.size.x, 1), c)
		y += 32.0


func _draw_road(ci: Node2D) -> void:
	var tb := TriBatch.new()
	var hw := data.width * 0.5
	_band(tb, -hw - 3.0, hw + 3.0, color("shoulder"))
	_band(tb, -hw, hw, color("road"))
	# Worn racing line: darker band that swings to the inside of corners.
	var m := data.size()
	for i in m:
		var j := (i + 1) % m
		var shift_i := clampf(-data.curvature[i] * 2600.0, -hw * 0.45, hw * 0.45)
		var shift_j := clampf(-data.curvature[j] * 2600.0, -hw * 0.45, hw * 0.45)
		var s := data.samples
		var n := data.normals
		var pts := PackedVector2Array([s[i] + n[i] * (shift_i - 7.0), s[j] + n[j] * (shift_j - 7.0),
				s[j] + n[j] * (shift_j + 7.0), s[i] + n[i] * (shift_i + 7.0)])
		var col := color("road_dark")
		col.a = 0.45
		tb.quad(pts[0], pts[1], pts[2], pts[3], col)
	# Grain of the surface.
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(data.id) + 3
	var grains := int(data.total_len * data.width / 90.0)
	for k in grains:
		var i := rng.randi_range(0, m - 1)
		var p := data.samples[i] + data.normals[i] * rng.randf_range(-hw + 1.0, hw - 1.0)
		var c := color("road_light") if rng.randf() < 0.5 else color("road_dark")
		tb.rect(Rect2(p.floor(), Vector2.ONE * (2.0 if rng.randf() < 0.15 else 1.0)), c)
	match data.surface:
		"dirt":
			for off in [-9.0, 9.0]:
				_band(tb, off - 1.5, off + 1.5, Color(color("road_dark"), 0.8))
			for k in 260:
				var i := rng.randi_range(0, m - 1)
				var p := data.samples[i] + data.normals[i] * rng.randf_range(-hw, hw)
				tb.rect(Rect2(p.floor(), Vector2(2, 2)), Color("6a6a6e"))
		"snow":
			# Packed snow drifting onto the edges, ice on corner exits.
			for side in [-1.0, 1.0]:
				for i in range(0, m, 2):
					var depth := 3.0 + 3.0 * sin(i * 0.37) + 2.0 * sin(i * 0.11)
					if depth <= 0.5:
						continue
					var j := (i + 2) % m
					if side < 0:
						_quad(tb, i, j, -hw, -hw + depth, color("ground_light"))
					else:
						_quad(tb, i, j, hw - depth, hw, color("ground_light"))
			for rgi in data.ice_ranges:
				_band(tb, -hw * 0.8, hw * 0.7, Color(0.75, 0.9, 1.0, 0.55), int(rgi[0]), int(rgi[1]))
				_band(tb, -hw * 0.3, -hw * 0.1, Color(1, 1, 1, 0.45), int(rgi[0]) + 2, int(rgi[1]) - 2)
		"wet":
			for k in 90:
				var i := rng.randi_range(0, m - 1)
				var p := data.samples[i] + data.normals[i] * rng.randf_range(-hw + 6.0, hw - 6.0)
				var t := data.tangents[i]
				var streak := rng.randf_range(6, 18)
				var pts := PackedVector2Array([p - t * streak, p + Vector2(-t.y, t.x) * 3.0, p + t * streak, p - Vector2(-t.y, t.x) * 3.0])
				tb.polygon(pts, Color(0.35, 0.34, 0.6, 0.5))
	tb.flush(ci)


func _draw_markings(ci: Node2D) -> void:
	var tb := TriBatch.new()
	var hw := data.width * 0.5
	var m := data.size()
	var line_col := color("line")
	if data.surface != "dirt":
		_band(tb, -hw + 2.0, -hw + 3.0, line_col)
		_band(tb, hw - 3.0, hw - 2.0, line_col)
	if pal.get("dashes", false):
		for i in m:
			if fmod(data.cum_len[i], 26.0) < 12.0:
				_quad(tb, i, (i + 1) % m, -0.5, 0.5, Color(line_col, 0.85))
	# Curbs on the outside (and inside) of tight corners.
	for i in m:
		var k := absf(data.curvature[i])
		if k < (1.0 / 420.0 if toy else 1.0 / 170.0):
			continue
		var stripe := int(data.cum_len[i] / (10.0 if toy else 7.0)) % 2 == 0
		var c := color("curb_a") if stripe else color("curb_b")
		if toy:
			c = Color("e8313f") if stripe else Color("f4f4f4")
		var j := (i + 1) % m
		var cw := 6.0 if toy else 4.0
		_quad(tb, i, j, hw, hw + cw, c)
		_quad(tb, i, j, -hw - cw, -hw, c)
	# Start / finish: checker strip across the road at sample 0.
	var s0 := data.samples[0]
	var t0 := data.tangents[0]
	var n0 := data.normals[0]
	var cells := int(data.width / 4.0)
	for row in 2:
		for c in cells:
			var black := (row + c) % 2 == 0
			var center := s0 + t0 * (row * 4.0 - 4.0) + n0 * (-hw + c * 4.0 + 2.0)
			var col := Color("141418") if black else Color("f2f2f2")
			var pts := PackedVector2Array([
				center + (-t0 - n0) * 2.0, center + (t0 - n0) * 2.0, center + (t0 + n0) * 2.0, center + (-t0 + n0) * 2.0])
			tb.polygon(pts, col)
	# Grid boxes.
	for slot in 4:
		var g := data.grid_slot(slot)
		var p: Vector2 = g["position"]
		var a: float = g["rotation"]
		tb.set_transform(p, a, Vector2.ONE)
		tb.rect(Rect2(-9, -6, 18, 12), Color(1, 1, 1, 0.7), false, 1.0)
		tb.reset_transform()
	tb.flush(ci)


func _draw_barriers(ci: Node2D) -> void:
	var tb := TriBatch.new()
	var style: String = "tires" if toy else str(pal.get("wall_style", "rail"))
	for side_pts in [wall_left, wall_right]:
		var pts: PackedVector2Array = side_pts
		var n := pts.size()
		var lines := PackedVector2Array()
		for i in n:
			var a := pts[i]
			var b := pts[(i + 1) % n]
			if a.distance_to(b) > 24.0:
				continue
			lines.append(a)
			lines.append(b)
		# shadow
		var shadow := PackedVector2Array()
		for p in lines:
			shadow.append(p + Vector2(1.5, 2.0))
		tb.multiline(shadow, Color(0, 0, 0, 0.35), 3.0)
		match style:
			"rail":
				tb.multiline(lines, color("wall_dark"), 3.0)
				tb.multiline(lines, color("wall"), 1.5)
				for i in range(0, n, 3):
					tb.rect(Rect2(pts[i] - Vector2(1, 1), Vector2(2, 2)), color("wall_dark"))
			"concrete":
				tb.multiline(lines, color("wall_dark"), 4.0)
				tb.multiline(lines, color("wall"), 2.0)
				for i in range(0, n, 4):
					var col := Color("ffd84a") if (i / 4) % 2 == 0 else Color("1a1a24")
					tb.rect(Rect2(pts[i] - Vector2(1, 1), Vector2(2, 2)), col)
			"tires":
				# Stacks of old tyres, like a toy race track.
				for i in range(0, n, 1):
					var tp := pts[i]
					tb.circle(tp + Vector2(1, 1.5), 2.6, Color(0, 0, 0, 0.35))
					tb.circle(tp, 2.6, Color("1c1c22"))
					tb.circle(tp + Vector2(-0.6, -0.6), 1.0, Color("4a4a56"))
			"fence":
				tb.multiline(lines, color("wall_dark"), 2.0)
				tb.multiline(lines, color("wall"), 1.0)
				for i in range(0, n, 2):
					tb.rect(Rect2(pts[i] - Vector2(1.5, 1.5), Vector2(3, 3)), color("wall_dark"))
	# Chevron signs at sharp corners (yellow arrows like a real mountain road).
	for ch in _chevrons:
		var p: Vector2 = ch["pos"]
		var dir: Vector2 = ch["dir"]
		tb.set_transform(p, dir.angle(), Vector2.ONE)
		tb.rect(Rect2(-3, -4, 6, 8), Color("1a1a1a"))
		tb.rect(Rect2(-2.5, -3.5, 5, 7), Color("f2c230"))
		tb.polyline(PackedVector2Array([Vector2(-1.5, -2.5), Vector2(1, 0), Vector2(-1.5, 2.5)]), Color("1a1a1a"), 1.0)
		tb.reset_transform()


# --- scenery ----------------------------------------------------------------
	tb.flush(ci)


func _wall_dist() -> float:
	return data.width * 0.5 + TrackData.WALL_MARGIN


## True if a circle at p with radius r keeps clear of every road + barrier.
func _clear(p: Vector2, r: float, near_idx: int) -> bool:
	var need := _wall_dist() + 4.0 + r
	var m := data.size()
	for o in range(-60, 61, 2):
		if p.distance_to(data.samples[posmod(near_idx + o, m)]) < need:
			return false
	for i in range(0, m, 6):
		if p.distance_to(data.samples[i]) < need:
			return false
	for b in _buildings:
		var rect: Rect2 = b["rect"]
		if rect.grow(r + 4.0).has_point(p):
			return false
	return true


func _place_scenery() -> void:
	var m := data.size()
	var wd := _wall_dist()
	# Chevrons on the outside of the sharpest corners.
	for i in range(0, m, 7):
		var k := data.curvature[i]
		if absf(k) > 1.0 / 95.0:
			# curvature > 0 bends right (towards +normal): the outside is the left
			var outer := -signf(k)
			var p := data.samples[i] + data.normals[i] * outer * (wd + 5.0)
			_chevrons.append({"pos": p, "dir": data.normals[i] * signf(k)})
	# Lamps every ~150 px on alternating sides.
	var step := int(150.0 / TrackData.SPACING)
	var flip := 1.0
	for i in range(0, m, step):
		flip = -flip
		var p := data.samples[i] + data.normals[i] * flip * (wd + 7.0)
		if _clear(p, 0.0, i):
			_lamps.append({"pos": p, "toward": -data.normals[i] * flip})
	if toy:
		_place_banners()
	match theme_name:
		"neon":
			_place_buildings()
			_scatter(["tree"], 70, 6.0, 60.0)
		"mountain":
			_scatter(["pine", "pine", "blossom", "rock"], 380, 5.0, 230.0)
		"forest":
			_scatter(["pine", "pine", "pine", "bush", "rock", "log"], 520, 4.0, 240.0)
		"snow":
			_scatter(["snowpine", "snowpine", "snowpine", "rock", "bank"], 420, 4.0, 240.0)


func _scatter(types: Array, count: int, min_gap: float, max_dist: float) -> void:
	count = int(count * float(Game.by_quality([0.5, 0.8, 1.0])))
	var m := data.size()
	var wd := _wall_dist()
	var tries := 0
	while _decor.size() < count and tries < count * 4:
		tries += 1
		var i := _rng.randi_range(0, m - 1)
		var side := -1.0 if _rng.randf() < 0.5 else 1.0
		var dist := wd + min_gap + pow(_rng.randf(), 1.6) * max_dist
		var p := data.samples[i] + data.normals[i] * side * dist + Vector2(_rng.randf_range(-10, 10), _rng.randf_range(-10, 10))
		var type: String = types[_rng.randi_range(0, types.size() - 1)]
		var r := _rng.randf_range(5.0, 11.0)
		if type == "rock" or type == "bush":
			r = _rng.randf_range(2.5, 5.0)
		elif type == "log":
			r = 4.0
		elif type == "bank":
			r = _rng.randf_range(6.0, 12.0)
		if theme_name == "mountain" and p.y > _shore - 36.0:
			continue
		if not _clear(p, r * 0.6, i):
			continue
		_decor.append({"type": type, "pos": p.round(), "r": r, "seed": _rng.randi()})
	# Draw back-to-front (top of screen first) so canopies overlap naturally.
	_decor.sort_custom(func(a, b): return a["pos"].y < b["pos"].y)


func _compute_shore_y() -> float:
	var max_y := -INF
	for p in data.samples:
		max_y = maxf(max_y, p.y)
	return max_y + data.width * 0.5 + TrackData.WALL_MARGIN + 60.0


func _place_buildings() -> void:
	var r := data.bounds
	var tries := 0
	while _buildings.size() < 70 and tries < 900:
		tries += 1
		var size := Vector2(_rng.randf_range(36, 110), _rng.randf_range(30, 90)).round()
		var pos := Vector2(_rng.randf_range(r.position.x, r.end.x - size.x), _rng.randf_range(r.position.y, r.end.y - size.y)).round()
		var rect := Rect2(pos, size)
		var center := rect.get_center()
		var idx := data.nearest(center)
		var half := size.length() * 0.5
		if center.distance_to(data.samples[idx]) < _wall_dist() + 6.0 + half:
			continue
		var overlap := false
		for b in _buildings:
			var other: Rect2 = b["rect"]
			if other.grow(6.0).intersects(rect):
				overlap = true
				break
		if overlap:
			continue
		var neon_cols := [Color("ff3da5"), Color("3ee0ff"), Color("a95cff"), Color("ffd84a")]
		_buildings.append({
			"rect": rect,
			"roof": Color("2a2648").lerp(Color("39345e"), _rng.randf()),
			"neon": neon_cols[_rng.randi_range(0, 3)],
			"word": NEON_WORDS[_rng.randi_range(0, NEON_WORDS.size() - 1)],
			"seed": _rng.randi(),
		})


func _place_banners() -> void:
	var m := data.size()
	var wd := _wall_dist()
	var cols := [Color("2f5fd8"), Color("f2c230"), Color("e8313f"), Color("2fae5a"), Color("f4f4f4")]
	var i := 20
	while i < m:
		var side := -1.0 if (i / 60) % 2 == 0 else 1.0
		var p := data.samples[i] + data.normals[i] * side * (wd + 12.0)
		if _clear(p, 8.0, i):
			_banners.append({"pos": p, "angle": data.tangents[i].angle(), "color": cols[_rng.randi_range(0, cols.size() - 1)],
					"word": NEON_WORDS[_rng.randi_range(0, NEON_WORDS.size() - 1)]})
		i += 45


## Sponsor banners standing along the track (Toy Racer style).
func _draw_banner(tb: TriBatch, b: Dictionary) -> void:
	var col: Color = b["color"]
	var word: String = b["word"]
	var w := PixelText.width_of(word) + 8.0
	tb.set_transform(b["pos"], b["angle"])
	tb.rect(Rect2(-w * 0.5 + 2, -4, w, 10), Color(0, 0, 0, 0.35))
	tb.rect(Rect2(-w * 0.5, -6, w, 10), Color("1a1a1a"))
	tb.rect(Rect2(-w * 0.5 + 1, -5, w - 2, 8), col)
	var txt := Color("1a1a1a") if col.get_luminance() > 0.6 else Color.WHITE
	PixelText.draw(tb, Vector2(-w * 0.5 + 4, -3.5), word, txt, 1.0, false)
	tb.reset_transform()


func _draw_scenery(ci: Node2D) -> void:
	var tb := TriBatch.new()
	for bn in _banners:
		_draw_banner(tb, bn)
	for b in _buildings:
		_draw_building(tb, b)
	for d in _decor:
		_draw_decor(tb, d)
	for l in _lamps:
		var p: Vector2 = l["pos"]
		var t: Vector2 = l["toward"]
		tb.rect(Rect2(p + Vector2(1, 2), Vector2(2, 2)), Color(0, 0, 0, 0.35))
		tb.rect(Rect2(p - Vector2(1, 1), Vector2(2, 2)), Color("3a3a48"))
		var head := p + t * 4.0
		tb.line(p, head, Color("3a3a48"), 1.0)
		tb.rect(Rect2(head - Vector2(1, 1), Vector2(2, 2)), color("lamp"))
		if not night:
			tb.circle(head + t * 2.0, 5.0, Color(color("lamp"), 0.12))
	tb.flush(ci)


func _draw_building(tb: TriBatch, b: Dictionary) -> void:
	var rect: Rect2 = b["rect"]
	var rng := RandomNumberGenerator.new()
	rng.seed = b["seed"]
	tb.rect(Rect2(rect.position + Vector2(4, 5), rect.size), Color(0, 0, 0, 0.45))
	tb.rect(rect, Color("16132a"))
	tb.rect(rect.grow(-2.0), b["roof"])
	# Roof clutter: AC units, vents, water tanks.
	for i in rng.randi_range(2, 6):
		var s := Vector2(rng.randi_range(4, 9), rng.randi_range(3, 7))
		var p := rect.position + Vector2(rng.randf_range(4, rect.size.x - s.x - 4), rng.randf_range(4, rect.size.y - s.y - 4))
		tb.rect(Rect2(p.round() + Vector2(1, 1), s), Color(0, 0, 0, 0.35))
		tb.rect(Rect2(p.round(), s), Color("4a4570"))
		tb.rect(Rect2(p.round(), Vector2(s.x, 1)), Color("625c8c"))
	# Neon outline + sign.
	var neon: Color = b["neon"]
	tb.rect(rect.grow(-1.0), neon, false, 1.0)
	var word: String = b["word"]
	var scale := 2.0 if rect.size.x > PixelText.width_of(word, 2.0) + 10.0 else 1.0
	PixelText.draw_centered(tb, rect.get_center(), word, neon, scale)


func _draw_decor(tb: TriBatch, d: Dictionary) -> void:
	var p: Vector2 = d["pos"]
	var r: float = d["r"]
	var rng := RandomNumberGenerator.new()
	rng.seed = d["seed"]
	match d["type"]:
		"pine", "tree":
			tb.circle(p + Vector2(3, 4), r, Color(0, 0, 0, 0.3))
			tb.circle(p, r, color("tree_dark"))
			tb.circle(p + Vector2(-1, -1), r * 0.75, color("tree"))
			tb.circle(p + Vector2(-2, -2), r * 0.4, color("tree_light"))
			tb.rect(Rect2(p - Vector2(0.5, 0.5), Vector2(1, 1)), color("tree_dark"))
		"snowpine":
			tb.circle(p + Vector2(3, 4), r, Color(0.2, 0.25, 0.4, 0.25))
			tb.circle(p, r, color("tree_dark"))
			tb.circle(p + Vector2(-1, -1), r * 0.75, color("tree"))
			for i in 5:
				var o := Vector2(rng.randf_range(-r * 0.6, r * 0.4), rng.randf_range(-r * 0.6, r * 0.4))
				tb.circle(p + o, r * rng.randf_range(0.2, 0.35), color("tree_light"))
		"blossom":
			tb.circle(p + Vector2(3, 4), r, Color(0, 0, 0, 0.3))
			tb.circle(p, r, color("accent_dark"))
			for i in 6:
				var o := Vector2(rng.randf_range(-r * 0.6, r * 0.5), rng.randf_range(-r * 0.6, r * 0.5))
				tb.circle(p + o, r * rng.randf_range(0.3, 0.5), color("accent"))
			tb.circle(p + Vector2(-r * 0.3, -r * 0.3), r * 0.25, Color("ffd6ea"))
		"rock":
			tb.circle(p + Vector2(1, 2), r, Color(0, 0, 0, 0.3))
			tb.circle(p, r, color("rock"))
			tb.circle(p + Vector2(-0.5, -0.5), r * 0.6, color("rock").lightened(0.2))
			if theme_name == "snow":
				tb.circle(p + Vector2(-0.5, -1.0), r * 0.5, Color.WHITE)
		"bush":
			tb.circle(p + Vector2(1, 2), r, Color(0, 0, 0, 0.3))
			tb.circle(p, r, color("tree"))
			tb.circle(p + Vector2(-1, -1), r * 0.5, color("tree_light"))
			if rng.randf() < 0.4:
				tb.rect(Rect2(p + Vector2(1, 0), Vector2(1, 1)), color("accent"))
		"log":
			var a := rng.randf() * PI
			tb.set_transform(p, a, Vector2.ONE)
			tb.rect(Rect2(-7, -1, 14, 4), Color(0, 0, 0, 0.3))
			tb.rect(Rect2(-7, -2, 14, 4), Color("6a4528"))
			tb.rect(Rect2(-7, -2, 14, 1), Color("8a6038"))
			tb.rect(Rect2(6, -2, 1, 4), Color("c09060"))
			tb.reset_transform()
		"bank":
			tb.circle(p + Vector2(1, 2), r, Color(0.5, 0.6, 0.8, 0.25))
			tb.circle(p, r, color("ground_light"))
			tb.circle(p + Vector2(r * 0.3, r * 0.3), r * 0.5, color("ground_dark"))


## Additive glow pass for the night city: lamps, neon signs, reflections.
func _draw_glow(ci: Node2D) -> void:
	var tex := FxTextures.radial_light()
	for l in _lamps:
		var p: Vector2 = l["pos"]
		var t: Vector2 = l["toward"]
		var c := Color(color("lamp"), 0.33)
		ci.draw_texture_rect(tex, Rect2(p + t * 14.0 - Vector2(26, 26), Vector2(52, 52)), false, c)
	for b in _buildings:
		var rect: Rect2 = b["rect"]
		var neon: Color = b["neon"]
		ci.draw_texture_rect(tex, rect.grow(14.0), false, Color(neon, 0.22))
		# Wet road reflection: a smeared streak of the sign colour on the road
		# closest to the building.
		var idx := data.nearest(rect.get_center())
		var sp := data.samples[idx]
		if sp.distance_to(rect.get_center()) < 170.0:
			var dir := (rect.get_center() - sp).normalized()
			var rp := sp + dir * data.width * 0.25
			ci.draw_texture_rect(tex, Rect2(rp - Vector2(10, 18), Vector2(20, 36)), false, Color(neon, 0.18))
