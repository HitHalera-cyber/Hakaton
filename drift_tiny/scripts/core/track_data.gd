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


func setup(def: Dictionary) -> void:
	id = def.get("id", "track")
	name = def.get("name", id)
	subtitle = def.get("subtitle", "")
	theme = def.get("theme", "mountain")
	surface = def.get("surface", "asphalt")
	music = def.get("music", "sunset")
	width = float(def.get("width", 54))
	target_lap = float(def.get("target_lap", 50))
	var pts := PackedVector2Array()
	for p in def.get("points", []):
		pts.append(Vector2(float(p[0]), float(p[1])))
	_sample(pts)
	if surface == "snow":
		_place_ice()


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
