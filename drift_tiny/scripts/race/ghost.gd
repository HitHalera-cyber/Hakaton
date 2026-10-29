class_name GhostCar
extends Node2D
## Replays a recorded lap as a see-through car. Recording happens through
## GhostCar.Recorder; the best lap per track is stored by SaveManager.

const RATE := 20.0   # samples per second

var frames: PackedFloat32Array = PackedFloat32Array()   # x, y, rotation, ...
var lap_time := 0.0
var car_id := "classic"
var stats: CarStats
var playing := false
var _t := 0.0


class Recorder:
	var frames := PackedFloat32Array()
	var _acc := 0.0

	func start() -> void:
		frames = PackedFloat32Array()
		_acc = 0.0

	func step(car: Node2D, delta: float) -> void:
		_acc += delta
		while _acc >= 1.0 / GhostCar.RATE:
			_acc -= 1.0 / GhostCar.RATE
			frames.append(snappedf(car.global_position.x, 0.1))
			frames.append(snappedf(car.global_position.y, 0.1))
			frames.append(snappedf(car.rotation, 0.001))


func load_from(d: Dictionary) -> bool:
	if d.is_empty() or not d.has("frames"):
		return false
	frames = PackedFloat32Array(d["frames"])
	lap_time = float(d.get("time", 0.0))
	car_id = str(d.get("car", "classic"))
	stats = CarStats.build(car_id, false)
	z_index = 4
	return frames.size() >= 6


static func to_dict(rec_frames: PackedFloat32Array, time: float, car: String) -> Dictionary:
	return {"time": time, "car": car, "frames": Array(rec_frames)}


func restart_lap() -> void:
	_t = 0.0
	playing = frames.size() >= 6
	visible = playing


func _process(delta: float) -> void:
	if not playing:
		return
	_t += delta
	var count := frames.size() / 3
	var f := _t * RATE
	var i := int(f)
	if i >= count - 1:
		playing = false
		visible = false
		return
	var a := f - i
	var p0 := Vector2(frames[i * 3], frames[i * 3 + 1])
	var p1 := Vector2(frames[i * 3 + 3], frames[i * 3 + 4])
	global_position = p0.lerp(p1, a)
	rotation = lerp_angle(frames[i * 3 + 2], frames[i * 3 + 5], a)
	queue_redraw()


func _draw() -> void:
	if stats == null:
		return
	CarPainter.draw_car(self, Transform2D.IDENTITY, stats.shape, stats.length, stats.width,
			Color(0.75, 0.85, 1.0), 0, 0, 0.0, false, 0.45)
	draw_set_transform(Vector2(0, -12).rotated(-rotation), -rotation, Vector2.ONE)
	PixelText.draw_centered(self, Vector2(0, -1), "GHOST", Color(0.75, 0.85, 1.0, 0.8))
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
