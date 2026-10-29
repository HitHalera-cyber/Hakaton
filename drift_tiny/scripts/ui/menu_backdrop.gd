class_name MenuBackdrop
extends Control
## Attract mode behind the menus: a real track with a CPU car drifting around
## it, rendered exactly like a race (low-res view scaled 2x).

var track_id := "mountain"
var car_id := "jdm"
var darken_left := true

var _vp: SubViewport
var _car: Car
var _cam: CameraController


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var svc := SubViewportContainer.new()
	svc.stretch = true
	svc.stretch_shrink = 2
	svc.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	svc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	svc.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(svc)
	_vp = SubViewport.new()
	_vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
	_vp.handle_input_locally = false
	svc.add_child(_vp)
	_build()
	var shade := Shade.new()
	shade.left = darken_left
	add_child(shade)


func _build() -> void:
	var data := Game.track_data(track_id)
	var world := Node2D.new()
	var track := Track.new()
	track.build(data)
	world.add_child(track)
	var skids := SkidLayer.new()
	world.add_child(skids)
	_car = Car.new()
	_car.night = track.night
	_car.setup(CarStats.build(car_id), data, skids)
	world.add_child(_car)
	var g := data.grid_slot(0)
	_car.place(g["position"], g["rotation"])
	_car.frozen = false
	_car.controller = AutopilotController.new(0.9, 0.0, 11)
	(_car.controller as AutopilotController).drift_happy = 1.0
	_vp.add_child(world)
	_cam = CameraController.new()
	_cam.targets = [_car]
	_cam.follow_speed = 3.0
	_vp.add_child(_cam)
	_cam.set_bounds(data.bounds)
	_cam.snap_to_targets()
	var layer := CanvasLayer.new()
	_vp.add_child(layer)
	var w := Weather.new()
	layer.add_child(w)
	w.setup(Weather.kind_for_theme(data.theme), _cam)


## Gradient that keeps menu text readable over the moving background.
class Shade:
	extends Control

	var left := true

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

	func _draw() -> void:
		var w := size.x
		if left:
			# Whole-pixel columns that never overlap (overlaps showed as stripes).
			var steps := 24
			var band := w * 0.55
			for i in steps:
				var a := 0.85 * (1.0 - float(i) / steps)
				var x0 := floorf(band * i / steps)
				var x1 := floorf(band * (i + 1) / steps)
				draw_rect(Rect2(x0, 0, x1 - x0, size.y), Color(0.03, 0.02, 0.09, a))
		draw_rect(Rect2(0, 0, w, size.y), Color(0.03, 0.02, 0.09, 0.15))
