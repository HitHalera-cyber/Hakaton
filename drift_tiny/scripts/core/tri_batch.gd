class_name TriBatch
extends RefCounted
## Collects untextured shapes as triangles and sends them to the GPU in a
## single draw call (flush). Drawing thousands of small rects, circles and
## lines one by one costs thousands of draw calls, which old PCs cannot
## afford; the track scenery goes through this batch instead.
## The method names mirror CanvasItem.draw_* so painting code reads the same.

var _pts := PackedVector2Array()
var _cols := PackedColorArray()
var _idx := PackedInt32Array()
var _xf := Transform2D.IDENTITY


func set_transform(pos: Vector2, angle := 0.0, scale := Vector2.ONE) -> void:
	_xf = Transform2D(angle, scale, 0.0, pos)


func draw_set_transform(pos: Vector2, angle := 0.0, scale := Vector2.ONE) -> void:
	set_transform(pos, angle, scale)


func reset_transform() -> void:
	_xf = Transform2D.IDENTITY


func size() -> int:
	return _pts.size()


func tri(a: Vector2, b: Vector2, c: Vector2, col: Color) -> void:
	var base := _pts.size()
	_pts.append(_xf * a)
	_pts.append(_xf * b)
	_pts.append(_xf * c)
	_cols.append(col)
	_cols.append(col)
	_cols.append(col)
	_idx.append(base)
	_idx.append(base + 1)
	_idx.append(base + 2)


func quad(a: Vector2, b: Vector2, c: Vector2, d: Vector2, col: Color) -> void:
	var base := _pts.size()
	_pts.append(_xf * a)
	_pts.append(_xf * b)
	_pts.append(_xf * c)
	_pts.append(_xf * d)
	for i in 4:
		_cols.append(col)
	_idx.append(base)
	_idx.append(base + 1)
	_idx.append(base + 2)
	_idx.append(base)
	_idx.append(base + 2)
	_idx.append(base + 3)


## Same arguments as CanvasItem.draw_rect (outline when filled is false).
func rect(r: Rect2, col: Color, filled := true, width := 1.0) -> void:
	if filled:
		quad(r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y), col)
		return
	var w := maxf(width, 1.0)
	rect(Rect2(r.position, Vector2(r.size.x, w)), col)
	rect(Rect2(Vector2(r.position.x, r.end.y - w), Vector2(r.size.x, w)), col)
	rect(Rect2(Vector2(r.position.x, r.position.y + w), Vector2(w, r.size.y - w * 2.0)), col)
	rect(Rect2(Vector2(r.end.x - w, r.position.y + w), Vector2(w, r.size.y - w * 2.0)), col)


func draw_rect(r: Rect2, col: Color, filled := true, width := 1.0) -> void:
	rect(r, col, filled, width)


## Filled circle as a triangle fan; few segments keep the pixel-art look.
func circle(center: Vector2, radius: float, col: Color) -> void:
	var segs := clampi(int(radius * 1.6), 6, 20)
	var base := _pts.size()
	_pts.append(_xf * center)
	_cols.append(col)
	for i in segs:
		var a := TAU * i / segs
		_pts.append(_xf * (center + Vector2(cos(a), sin(a)) * radius))
		_cols.append(col)
	for i in segs:
		_idx.append(base)
		_idx.append(base + 1 + i)
		_idx.append(base + 1 + (i + 1) % segs)


## Convex polygon (fan from the first point).
func polygon(points: PackedVector2Array, col: Color) -> void:
	for i in range(1, points.size() - 1):
		tri(points[0], points[i], points[i + 1], col)


func line(a: Vector2, b: Vector2, col: Color, width := 1.0) -> void:
	var d := b - a
	if d.length_squared() < 0.0001:
		return
	var n := Vector2(-d.y, d.x).normalized() * maxf(width, 1.0) * 0.5
	quad(a + n, b + n, b - n, a - n, col)


func polyline(points: PackedVector2Array, col: Color, width := 1.0) -> void:
	for i in points.size() - 1:
		line(points[i], points[i + 1], col, width)


## Pairs of points, like CanvasItem.draw_multiline.
func multiline(points: PackedVector2Array, col: Color, width := 1.0) -> void:
	for i in range(0, points.size() - 1, 2):
		line(points[i], points[i + 1], col, width)


## Sends everything to the canvas item in one draw call and empties the batch.
## Must be called while that item is drawing (its _draw or "draw" signal).
func flush(ci: CanvasItem) -> void:
	if not _idx.is_empty():
		RenderingServer.canvas_item_add_triangle_array(ci.get_canvas_item(), _idx, _pts, _cols)
	_pts = PackedVector2Array()
	_cols = PackedColorArray()
	_idx = PackedInt32Array()
	_xf = Transform2D.IDENTITY
