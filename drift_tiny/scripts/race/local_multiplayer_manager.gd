class_name LocalMultiplayerManager
extends Node
## Screen layout for one or two players on one PC:
##  * one player — one full-screen view;
##  * two players, "split" — two side-by-side views, each with its own
##    camera, HUD and minimap (both views render the same World2D);
##  * two players, "shared" — one camera framing both cars, two compact HUDs;
##    if the cars get too far apart the trailing one is brought back.
## Each view renders the world at half resolution (480x270 for a full screen)
## and is scaled up 2x with nearest filtering for crisp pixels.

var race: Node
var world: Node2D
var humans: Array = []
var cars: Array = []
var track_data: TrackData
var ghost: Node2D
var shared_view := false
var cameras: Array = []
var huds: Array = []

var _shared_far_t := 0.0


func setup(the_race: Node, the_world: Node2D, human_cars: Array, all_cars: Array, data: TrackData,
		ghost_car: Node2D, shared: bool) -> void:
	race = the_race
	world = the_world
	humans = human_cars
	cars = all_cars
	track_data = data
	ghost = ghost_car
	shared_view = shared and humans.size() == 2
	build_views()


func build_views() -> void:
	var bg := ColorRect.new()
	bg.color = Color("08060f")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	race.add_child(bg)
	var row := HBoxContainer.new()
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.add_theme_constant_override("separation", 4)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	race.add_child(row)
	var view_count := 1 if humans.size() == 1 or shared_view else 2
	var first_vp: SubViewport = null
	var weather_kind := Weather.kind_for_theme(track_data.theme)
	for i in view_count:
		var slot := Control.new()
		slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slot.size_flags_vertical = Control.SIZE_EXPAND_FILL
		slot.clip_contents = true
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_child(slot)
		var svc := SubViewportContainer.new()
		svc.stretch = true
		svc.stretch_shrink = 2
		svc.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		svc.mouse_filter = Control.MOUSE_FILTER_IGNORE
		svc.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		slot.add_child(svc)
		var vp := SubViewport.new()
		vp.canvas_item_default_texture_filter = Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST
		vp.handle_input_locally = false
		svc.add_child(vp)
		if i == 0:
			vp.add_child(world)
			first_vp = vp
		else:
			vp.world_2d = first_vp.world_2d
		var cam := CameraController.new()
		cam.shake_enabled = bool(SaveManager.get_setting("camera_shake", true))
		vp.add_child(cam)
		cam.set_bounds(track_data.bounds)
		if view_count == 1:
			cam.targets = humans.duplicate()
		else:
			cam.targets = [humans[i]]
		cam.snap_to_targets()
		cameras.append(cam)
		var layer := CanvasLayer.new()
		vp.add_child(layer)
		var weather := Weather.new()
		layer.add_child(weather)
		weather.setup(weather_kind, cam)
		if view_count == 2 or humans.size() == 1:
			_add_hud(slot, humans[i], view_count == 2)
		else:
			# Shared screen: two compact HUDs side by side over one view.
			var halves := HBoxContainer.new()
			halves.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
			halves.mouse_filter = Control.MOUSE_FILTER_IGNORE
			slot.add_child(halves)
			for h in humans:
				var half := Control.new()
				half.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				half.mouse_filter = Control.MOUSE_FILTER_IGNORE
				halves.add_child(half)
				_add_hud(half, h, true)
			# One timer / minimap is enough on a shared screen.
			(huds[-1] as RaceHUD).show_race_info = false
	for c in cars:
		(c as Car).set_shake_callback(_shake_for.bind(c))


func _add_hud(parent: Control, car: Car, compact: bool) -> void:
	var hud := RaceHUD.new()
	hud.compact = compact
	parent.add_child(hud)
	hud.bind(car, race, cars, track_data)
	hud.ghost = ghost
	huds.append(hud)


func _shake_for(amount: float, car: Car) -> void:
	for cam in cameras:
		if car in (cam as CameraController).targets:
			(cam as CameraController).shake(amount)


## Shared camera: if the cars drift too far apart, bring the trailing one
## back next to the leader instead of letting it leave the screen.
func keep_together(delta: float, progress: Callable) -> void:
	if not shared_view or cameras.is_empty():
		return
	var cam := cameras[0] as CameraController
	if cam.targets_fit():
		_shared_far_t = 0.0
		return
	_shared_far_t += delta
	if _shared_far_t < 1.5:
		return
	_shared_far_t = 0.0
	var a := humans[0] as Car
	var b := humans[1] as Car
	var lead := a if float(progress.call(a)) >= float(progress.call(b)) else b
	var trail := b if lead == a else a
	var idx := track_data.advance(lead.track_idx, -40.0)
	trail.global_position = track_data.samples[idx] + track_data.normals[idx] * 10.0
	trail.rotation = track_data.tangents[idx].angle()
	trail.velocity = lead.velocity * 0.8
	trail.respawn_soft()
	message_for(trail, "CATCH UP", UiTheme.CYAN, 1.0, false)


func message_all(text: String, col: Color, dur: float) -> void:
	for h in huds:
		(h as RaceHUD).show_message(text, col, dur)


func message_for(car: Car, text: String, col: Color, dur: float, big := true) -> void:
	for h in huds:
		if (h as RaceHUD).car == car:
			(h as RaceHUD).show_message(text, col, dur, big)
