class_name SkidLayer
extends Node2D
## Tyre marks. A fixed ring buffer of segments, drawn in a handful of
## draw_multiline calls (one per alpha band) so thousands of marks stay cheap.

const MAX_SEGMENTS := 3600
const BANDS := 3

var mark_color := Color(0.06, 0.06, 0.08)
var loose_color := Color(0.25, 0.18, 0.1)

var _points: Array = []    # per band: PackedVector2Array of segment pairs
var _cursor: Array = []
var _dirty := false


func _ready() -> void:
	z_index = 1
	for b in BANDS * 2:
		var arr := PackedVector2Array()
		arr.resize(MAX_SEGMENTS / BANDS * 2)
		arr.fill(Vector2.ZERO)
		_points.append(arr)
		_cursor.append(0)


func add(a: Vector2, b: Vector2, alpha: float, surface: String) -> void:
	if a.distance_squared_to(b) < 0.25:
		return
	var band := clampi(int(alpha * BANDS), 0, BANDS - 1)
	if surface in ["dirt", "grass", "sand", "snow", "snowbank"]:
		band += BANDS
	var arr: PackedVector2Array = _points[band]
	var c: int = _cursor[band]
	arr[c] = a
	arr[c + 1] = b
	_points[band] = arr
	_cursor[band] = (c + 2) % arr.size()
	_dirty = true


func clear_marks() -> void:
	for b in _points.size():
		var arr: PackedVector2Array = _points[b]
		arr.fill(Vector2.ZERO)
		_points[b] = arr
	_dirty = true


func _process(_delta: float) -> void:
	if _dirty:
		_dirty = false
		queue_redraw()


func _draw() -> void:
	for b in _points.size():
		var loose := b >= BANDS
		var band := b % BANDS
		var col := loose_color if loose else mark_color
		col.a = 0.18 + 0.16 * band
		draw_multiline(_points[b], col, 1.0)
