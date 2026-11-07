class_name TrackData
extends RefCounted
## Geometry of a track: a closed Catmull-Rom spline through the control points
## of data/tracks.json, sampled every few pixels. Everything else (road mesh,
## barriers, lap progress, minimap) is built from these samples.
## tools/check_tracks.py uses the same maths to validate new tracks.

const SPACING := 6.0
const WALL_MARGIN := 18.0  # grass between the road edge and the barrier

var id := ""
var name := ""
var subtitle := ""
var theme := "mountain"
var surface := "asphalt"
var music := "sunset"
var width := 54.0
var target_lap := 50.0

var samples := PackedVector2Array()
var tangents := PackedVector2Array()
var normals := PackedVector2Array()   # points to the right of the driving direction
var cum_len := PackedFloat32Array()   # distance along the road at each sample
var curvature := PackedFloat32Array() # signed, 1/px
var total_len := 0.0
var bounds := Rect2()

## Index ranges of samples covered with ice (snow track) — lower grip.
var ice_ranges: Array = []
## Drift zones: [start, end] sample index ranges around the sharpest corners
## (end may run past the last sample; it wraps). Drifting through a whole zone
## earns a grade and bonus points.
var drift_zones: Array = []
## Hazards on the road: {type: oil|gravel|ice|boost, idx, pos, r}.
var hazards: Array = []
## Drift-only shortcuts: {a, b (Vector2 ends on the centre line), i, j, hw}.
var shortcuts: Array = []
## Gymkhana arena: an open lot instead of a road loop.
var arena := false
var arena_rect := Rect2()
var posts: Array = []        # donut posts (Vector2)
var cones: Array = []        # slalom cones (Vector2)
const SHORTCUT_HW := 17.0


## reverse: drive the loop the other way (same start line). It gets its own
## id ("<id>_rev"), so records, ghosts and scenery are separate.
func setup(def: Dictionary, reverse := false) -> void:
	id = def.get("id", "track")
	name = def.get("name", id)
	if reverse:
		id += "_rev"
		name += " (R)"
	subtitle = def.get("subtitle", "")
	theme = def.get("theme", "mountain")
	surface = def.get("surface", "asphalt")
	music = def.get("music", "sunset")
	width = float(def.get("width", 54))
	target_lap = float(def.get("target_lap", 50))
	var pts := PackedVector2Array()
	for p in def.get("points", []):
		pts.append(Vector2(float(p[0]), float(p[1])))
	if reverse and pts.size() > 2:
		var rev := PackedVector2Array([pts[0]])
		for k in range(pts.size() - 1, 0, -1):
			rev.append(pts[k])
		pts = rev
	_sample(pts)
	if surface == "snow":
		_place_ice()
	# Roughly one zone every 600 px of road.
	_place_drift_zones(clampi(int(total_len / 600.0), 7, 10))
	_place_hazards()
	_find_shortcuts()


## The gymkhana lot. It still has a (hidden) loop of samples so the car's
## track queries work; the loop's width covers the whole lot, so everywhere
## counts as road.
func setup_arena() -> void:
	arena = true
	id = "arena"
	name = "Gymkhana Arena"
	subtitle = "Donuts, figure eights, ramps"
	theme = "arena"
	surface = "asphalt"
	music = "menu"
	width = 1000.0
	arena_rect = Rect2(0, 0, 1100, 760)
	var c := arena_rect.get_center()
	var pts := PackedVector2Array()
	for k in 24:
		var a := TAU * k / 24.0
		pts.append(c + Vector2(cos(a) * 280.0, sin(a) * 170.0))
	_sample(pts)
	bounds = arena_rect.grow(140.0)
	posts = [c + Vector2(-230, 0), c + Vector2(230, 0), c + Vector2(0, -230), c + Vector2(0, 230)]
	for k in 7:
		cones.append(Vector2(220 + k * 110, 90 + (k % 2) * 30))
	hazards = [
		{"type": "ramp", "idx": 0, "pos": c + Vector2(0, -20), "r": 13.0},
		{"type": "ramp", "idx": 0, "pos": Vector2(150, 620), "r": 13.0},
		{"type": "boost", "idx": 0, "pos": Vector2(950, 620), "r": 9.0},
		{"type": "boost", "idx": 0, "pos": Vector2(950, 160), "r": 9.0},
		{"type": "oil", "idx": 0, "pos": c + Vector2(-120, 150), "r": 14.0},
	]


func _sample(pts: PackedVector2Array) -> void:
	samples.clear()
	var n := pts.size()
	for i in n:
		var p0 := pts[posmod(i - 1, n)]
		var p1 := pts[i]
		var p2 := pts[(i + 1) % n]
		var p3 := pts[(i + 2) % n]
		var steps := maxi(2, ceili(p1.distance_to(p2) / SPACING))
		for s in steps:
			samples.append(_catmull(p0, p1, p2, p3, float(s) / steps))
	var m := samples.size()
	tangents.resize(m)
	normals.resize(m)
	cum_len.resize(m)
	curvature.resize(m)
	var acc := 0.0
	for i in m:
		var prev := samples[posmod(i - 1, m)]
		var next := samples[(i + 1) % m]
		var t := (next - prev).normalized()
		tangents[i] = t
		normals[i] = Vector2(-t.y, t.x)
		if i > 0:
			acc += samples[i].distance_to(samples[i - 1])
		cum_len[i] = acc
	total_len = acc + samples[m - 1].distance_to(samples[0])
	for i in m:
		var a := tangents[posmod(i - 4, m)]
		var b := tangents[(i + 4) % m]
		curvature[i] = a.angle_to(b) / (SPACING * 8.0)
	var r := Rect2(samples[0], Vector2.ZERO)
	for p in samples:
		r = r.expand(p)
	bounds = r.grow(width + 260.0)


static func _catmull(p0: Vector2, p1: Vector2, p2: Vector2, p3: Vector2, t: float) -> Vector2:
	var t2 := t * t
	var t3 := t2 * t
	return 0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)


func _place_ice() -> void:
	# Ice sits at the exit of the three tightest corners.
	var m := samples.size()
	var scored: Array = []
	for i in range(0, m, 10):
		scored.append([absf(curvature[i]), i])
	scored.sort_custom(func(a, b): return a[0] > b[0])
	var used: Array = []
	for entry in scored:
		var idx: int = entry[1]
		var far := true
		for u in used:
			if absi(u - idx) < 80 and absi(u - idx) < m - 80:
				far = false
		if far:
			used.append(idx)
			ice_ranges.append([idx + 4, idx + 22])
		if used.size() >= 3:
			break


## The sharpest corners, at least 50 samples apart, become drift zones.
func _place_drift_zones(count: int) -> void:
	var m := samples.size()
	var scored: Array = []
	for i in range(0, m, 4):
		# Smoothed curvature so a long bend beats a single kink.
		var k := 0.0
		for o in range(-8, 9, 2):
			k += absf(curvature[posmod(i + o, m)])
		scored.append([k, i])
	scored.sort_custom(func(a, b): return a[0] > b[0])
	for entry in scored:
		var idx: int = entry[1]
		var far := true
		for z in drift_zones:
			var c: int = (int(z[0]) + int(z[1])) / 2
			var d := absi(c - idx)
			if mini(d, m - d) < 50:
				far = false
		# Keep zones off the start line.
		if mini(idx, m - idx) < 40:
			far = false
		if far:
			drift_zones.append([idx - 14, idx + 22])
		if drift_zones.size() >= count:
			break
	drift_zones.sort_custom(func(a, b): return a[0] < b[0])


## Oil, gravel and ice patches plus boost pads, spread along the lap
## (never on the start line). Boost pads sit on the straighter parts.
func _place_hazards() -> void:
	var m := samples.size()
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(id) + 99
	var plan := ["boost", "boost", "boost", "boost", "oil", "oil", "oil", "gravel", "gravel"]
	if surface != "snow":
		plan.append("ice")
	var used: Array = []
	for type in plan:
		for attempt in 40:
			var i := rng.randi_range(45, m - 45)
			if type == "boost" and absf(curvature[i]) > 1.0 / 300.0:
				continue
			var far := true
			for u in used:
				var d := absi(int(u) - i)
				if mini(d, m - d) < 35:
					far = false
			if not far:
				continue
			var r: float = {"boost": 9.0, "oil": 11.0, "gravel": 16.0, "ice": 15.0}[type]
			var lat := 0.0 if type == "boost" else rng.randf_range(-width * 0.5 + r + 4.0, width * 0.5 - r - 4.0)
			hazards.append({"type": type, "idx": i, "pos": samples[i] + normals[i] * lat, "r": r})
			used.append(i)
			break


## Looks for a straight chord across the infield that skips a good piece of
## road without touching any other part of the track. Gates at its ends only
## let drifting cars through (see Track / Car).
func _find_shortcuts() -> void:
	var m := samples.size()
	var clear_d := width * 0.5 + WALL_MARGIN + 6.0
	var best := {}
	var best_gain := 0.0
	for i in range(30, m, 5):
		for step in range(50, 340, 5):
			var j := (i + step) % m
			var along := fmod(cum_len[j] - cum_len[i] + total_len, total_len)
			if along < 380.0 or along > 2000.0:
				continue
			var a := samples[i]
			var b := samples[j]
			var L := a.distance_to(b)
			if L < width + 60.0 or L > 420.0:
				continue
			var dir := (b - a) / L
			if tangents[i].dot(dir) < 0.1 or tangents[j].dot(dir) < 0.1:
				continue
			var gain := along - L
			if gain <= best_gain:
				continue
			# The chord must keep clear of every other part of the road.
			var ok := true
			var t := clear_d + 10.0
			while t < L - clear_d - 10.0 and ok:
				var p := a + dir * t
				for k in range(0, m, 3):
					if p.distance_to(samples[k]) < clear_d:
						ok = false
						break
				t += 8.0
			if ok:
				best_gain = gain
				best = {"a": a, "b": b, "i": i, "j": j, "hw": SHORTCUT_HW}
	if not best.is_empty() and (best["i"] < m - 20 and best["i"] > 20):
		shortcuts.append(best)


## True if p lies on a shortcut's road.
func in_shortcut(p: Vector2) -> bool:
	for sc in shortcuts:
		if Geometry2D.get_closest_point_to_segment(p, sc["a"], sc["b"]).distance_to(p) < float(sc["hw"]):
			return true
	return false


## Hazard under a point (searched near sample idx), or "".
func hazard_at(pos: Vector2, idx: int) -> String:
	var m := samples.size()
	for h in hazards:
		if arena:
			if pos.distance_to(h["pos"]) < float(h["r"]):
				return h["type"]
			continue
		var d := absi(int(h["idx"]) - idx)
		if mini(d, m - d) > 12:
			continue
		var hp: Vector2 = h["pos"]
		if pos.distance_to(hp) < float(h["r"]):
			return h["type"]
	return ""


## Index of the drift zone containing sample idx, or -1.
func zone_at(idx: int) -> int:
	if idx < 0:
		return -1
	var m := samples.size()
	for z in drift_zones.size():
		var a: int = drift_zones[z][0]
		var b: int = drift_zones[z][1]
		if posmod(idx - a, m) <= b - a:
			return z
	return -1


func size() -> int:
	return samples.size()


## Nearest sample to pos. With a hint (last known index) only nearby samples
## are searched, which keeps this cheap enough to call every frame.
func nearest(pos: Vector2, hint := -1) -> int:
	var m := samples.size()
	var best := 0
	var best_d := INF
	if hint >= 0:
		for o in range(-40, 41):
			var i := posmod(hint + o, m)
			var d := pos.distance_squared_to(samples[i])
			if d < best_d:
				best_d = d
				best = i
		# If the local search ended up far away (respawn, teleport), fall back.
		if best_d < pow(width * 2.0, 2):
			return best
	for i in m:
		var d := pos.distance_squared_to(samples[i])
		if d < best_d:
			best_d = d
			best = i
	return best


## Signed distance from the centre line (positive = right side).
func lateral(pos: Vector2, idx: int) -> float:
	return (pos - samples[idx]).dot(normals[idx])


func is_ice(idx: int) -> bool:
	for r in ice_ranges:
		if idx >= int(r[0]) and idx <= int(r[1]):
			return true
	return false


## Index that lies `dist` pixels further along the road.
func advance(idx: int, dist: float) -> int:
	return posmod(idx + int(round(dist / SPACING)), samples.size())


## Start grid slot: position and heading for slot n (0-based), behind the line.
func grid_slot(n: int) -> Dictionary:
	if arena:
		var p := Vector2(arena_rect.get_center().x - 30.0 + n * 30.0, arena_rect.end.y - 70.0)
		return {"position": p, "rotation": -PI * 0.5, "index": nearest(p)}
	var row := n / 2
	var side := -1.0 if n % 2 == 0 else 1.0
	var idx := posmod(-6 - row * 6, samples.size())
	var pos := samples[idx] + normals[idx] * side * width * 0.22
	return {"position": pos, "rotation": tangents[idx].angle(), "index": idx}


## Offset curve for a barrier on one side (side = 1 right, -1 left). Points
## that fold over in tight corners (closer to the centre line than intended)
## are dropped, so the barrier never cuts into the road.
func wall_points(side: float, extra := 0.0) -> PackedVector2Array:
	var d := width * 0.5 + WALL_MARGIN + extra
	var out := PackedVector2Array()
	var m := samples.size()
	for i in m:
		var p := samples[i] + normals[i] * side * d
		var ok := true
		for o in range(-30, 31, 2):
			var j := posmod(i + o, m)
			if p.distance_to(samples[j]) < d - 1.5:
				ok = false
				break
		if ok:
			out.append(p)
	return out


## Distance from a point to the centre line, searched near idx.
func center_distance(pos: Vector2, idx: int) -> float:
	return absf(lateral(pos, idx))
