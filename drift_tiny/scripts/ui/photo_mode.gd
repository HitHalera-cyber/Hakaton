class_name PhotoMode
extends Control
## Photo mode (pause menu or F2): the race freezes, the HUD hides and the
## camera flies freely. Arrows/WASD or the left stick move, Q/E, the mouse
## wheel or the triggers zoom, Enter / A saves a PNG to the photos folder.

const MOVE_SPEED := 320.0

var race: RaceManager
var active := false
var _cam: CameraController
var _zoom0 := Vector2.ONE
var _label: Label
var _hidden: Array = []


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	theme = UiTheme.get_theme()
	visible = false
	_label = UiTheme.label("", 14, UiTheme.TEXT)
	_label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	_label.offset_top = -34
	_label.offset_bottom = -10
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_label)


func open() -> void:
	if active or race.views.cameras.is_empty():
		return
	active = true
	visible = true
	get_tree().paused = true
	_cam = race.views.cameras[0]
	_zoom0 = _cam.zoom
	if _cam.post_material:
		_cam.post_material.set_shader_parameter("subpixel", Vector2.ZERO)
	_hidden.clear()
	for h in race.views.huds:
		if (h as CanvasItem).visible:
			(h as CanvasItem).visible = false
			_hidden.append(h)
	_show_help()


func close() -> void:
	active = false
	visible = false
	_cam.zoom = _zoom0
	_cam.snap_to_targets()
	for h in _hidden:
		(h as CanvasItem).visible = true
	get_tree().paused = false


func _show_help() -> void:
	_label.text = tr("PHOTO MODE · Arrows / stick — move · Q / E — zoom · Enter / A — save photo · Esc — back")


func _process(delta: float) -> void:
	if not active:
		return
	var v := Vector2.ZERO
	if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A):
		v.x -= 1.0
	if Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D):
		v.x += 1.0
	if Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W):
		v.y -= 1.0
	if Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S):
		v.y += 1.0
	var stick := Vector2(Input.get_joy_axis(0, JOY_AXIS_LEFT_X), Input.get_joy_axis(0, JOY_AXIS_LEFT_Y))
	if stick.length() > 0.2:
		v += stick
	var z := 0.0
	if Input.is_key_pressed(KEY_E):
		z += 1.0
	if Input.is_key_pressed(KEY_Q):
		z -= 1.0
	z += Input.get_joy_axis(0, JOY_AXIS_TRIGGER_RIGHT) - Input.get_joy_axis(0, JOY_AXIS_TRIGGER_LEFT)
	# Real (unscaled) time: the tree is paused but this node keeps running.
	delta /= maxf(Engine.time_scale, 0.01)
	_zoom_by(z * delta * 1.5)
	var p := _cam.global_position + v.limit_length(1.0) * MOVE_SPEED * delta / _cam.zoom.x
	var lim := Rect2(_cam.limit_left, _cam.limit_top, _cam.limit_right - _cam.limit_left, _cam.limit_bottom - _cam.limit_top)
	var half := _cam.get_viewport_rect().size * 0.5 / _cam.zoom.x
	p.x = clampf(p.x, lim.position.x + half.x, maxf(lim.end.x - half.x, lim.position.x + half.x))
	p.y = clampf(p.y, lim.position.y + half.y, maxf(lim.end.y - half.y, lim.position.y + half.y))
	_cam.global_position = p.round()


func _zoom_by(amount: float) -> void:
	var k := clampf(_cam.zoom.x * exp(amount), 0.6, 3.0)
	_cam.zoom = Vector2(k, k)


func _unhandled_input(event: InputEvent) -> void:
	if not active:
		return
	if event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel"):
		close()
	elif event.is_action_pressed("ui_accept"):
		capture()
	elif event is InputEventMouseButton and event.pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_zoom_by(0.12)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_zoom_by(-0.12)
		else:
			return
	else:
		return
	get_viewport().set_input_as_handled()


## Saves the current frame without the help line; returns the file path.
func capture() -> String:
	_label.visible = false
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute("user://photos")
	var stamp := Time.get_datetime_string_from_system().replace(":", "-").replace("T", "_")
	var path := "user://photos/drift_tiny_%s_%d.png" % [stamp, Time.get_ticks_msec() % 1000]
	img.save_png(path)
	_label.visible = true
	_label.text = tr("Saved: %s") % ProjectSettings.globalize_path(path)
	AudioManager.play("reward", 1.4, -8.0)
	return path
