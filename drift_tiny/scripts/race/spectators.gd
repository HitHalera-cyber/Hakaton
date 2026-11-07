class_name Spectators
extends Node2D
## Crowds standing behind the barriers of every drift zone, and the camera
## flashes they fire while a car drifts through their zone.

const FLASH_LIFE := 0.12

var track: Track
var cars: Array = []
var crowd: Array = []        # {pos, color, zone}
var _by_zone: Dictionary = {}
var _flashes: Array = []     # {pos, t}
var _rng := RandomNumberGenerator.new()
var arena_mode := false       # gymkhana: everyone cheers for any drift


func add_person(pos: Vector2, col: Color, zone: int) -> void:
	var person := {"pos": pos, "color": col, "zone": zone}
	crowd.append(person)
	if not _by_zone.has(zone):
		_by_zone[zone] = []
	(_by_zone[zone] as Array).append(person)


func _ready() -> void:
	z_index = 8
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	material = mat


## Places people on the outside of each drift zone (called by Track).
func populate(t: Track) -> void:
	track = t
	_rng.seed = hash(t.data.id) + 5
	var data := t.data
	var m := data.size()
	var wd := t._wall_dist()
	var shirts := [Color("e8313f"), Color("2f7ee8"), Color("f2c230"), Color("2fae5a"), Color("f4f4f4"), Color("ff5fb8"), Color("9a4ef0")]
	for z in data.drift_zones.size():
		var a: int = data.drift_zones[z][0]
		var b: int = data.drift_zones[z][1]
		var mid := posmod((a + b) / 2, m)
		var outer := -signf(data.curvature[mid])
		if outer == 0.0:
			outer = 1.0
		for k in range(a, b, 2):
			var i := posmod(k, m)
			for row in 2:
				if _rng.randf() < 0.35:
					continue
				var p := data.samples[i] + data.normals[i] * outer * (wd + 7.0 + row * 5.0)
				p += Vector2(_rng.randf_range(-1.5, 1.5), _rng.randf_range(-1.5, 1.5))
				if not t._clear(p, 0.0, i):
					continue
				var person := {"pos": p.round(), "color": shirts[_rng.randi_range(0, shirts.size() - 1)], "zone": z}
				crowd.append(person)
				if not _by_zone.has(z):
					_by_zone[z] = []
				(_by_zone[z] as Array).append(person)


## Drawn by Track in the scenery batch: a shirt and a head per person.
func draw_crowd(tb: TriBatch) -> void:
	for p in crowd:
		var pos: Vector2 = p["pos"]
		tb.rect(Rect2(pos + Vector2(1, 1), Vector2(3, 3)), Color(0, 0, 0, 0.3))
		tb.rect(Rect2(pos - Vector2(1.5, 1.5), Vector2(3, 3)), p["color"])
		tb.rect(Rect2(pos - Vector2(0.5, 1.5), Vector2(1, 1)), Color("f0c8a0"))


func _process(delta: float) -> void:
	for f in _flashes:
		f["t"] = float(f["t"]) + delta
	while not _flashes.is_empty() and float(_flashes[0]["t"]) > FLASH_LIFE:
		_flashes.pop_front()
	for c in cars:
		var car := c as Car
		if not is_instance_valid(car) or not car.drifting:
			continue
		var z := 0 if arena_mode else car.scoring.zone_id
		if z < 0 or not _by_zone.has(z):
			continue
		var people: Array = _by_zone[z]
		# More flashes for bigger angles.
		if _rng.randf() < delta * (6.0 + car.slip_deg * 0.3):
			var who: Dictionary = people[_rng.randi_range(0, people.size() - 1)]
			_flashes.append({"pos": who["pos"], "t": 0.0})
	queue_redraw()


func _draw() -> void:
	if _flashes.is_empty():
		return
	var tb := TriBatch.new()
	for f in _flashes:
		var p: Vector2 = f["pos"]
		var a := 1.0 - float(f["t"]) / FLASH_LIFE
		tb.circle(p, 5.0 * a + 1.0, Color(1, 1, 1, 0.35 * a))
		tb.line(p - Vector2(5, 0), p + Vector2(5, 0), Color(1, 1, 1, 0.8 * a), 1.0)
		tb.line(p - Vector2(0, 5), p + Vector2(0, 5), Color(1, 1, 1, 0.8 * a), 1.0)
	tb.flush(self)
