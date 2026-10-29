extends Node
## Creates every input action at startup (keyboard + two gamepads) and applies
## the player's key remaps from the save file.

const ACTIONS := ["accel", "brake", "left", "right", "handbrake", "reset"]
const ACTION_LABELS := {
	"accel": "Throttle", "brake": "Brake / Reverse", "left": "Steer left",
	"right": "Steer right", "handbrake": "Handbrake", "reset": "Back on track",
}

## Default keyboard layout: [keycode, location] pairs. Location tells left and
## right Shift apart (KEY_LOCATION_* — Godot 4.3+).
var DEFAULT_KEYS := {
	"p1_accel": [[KEY_W, 0]],
	"p1_brake": [[KEY_S, 0]],
	"p1_left": [[KEY_A, 0]],
	"p1_right": [[KEY_D, 0]],
	"p1_handbrake": [[KEY_SHIFT, 1], [KEY_SPACE, 0]],
	"p1_reset": [[KEY_R, 0]],
	"p2_accel": [[KEY_UP, 0]],
	"p2_brake": [[KEY_DOWN, 0]],
	"p2_left": [[KEY_LEFT, 0]],
	"p2_right": [[KEY_RIGHT, 0]],
	"p2_handbrake": [[KEY_SHIFT, 2], [KEY_CTRL, 2], [KEY_KP_0, 0]],
	"p2_reset": [[KEY_BACKSPACE, 0]],
}

var _location_supported := false


func _ready() -> void:
	_location_supported = "location" in InputEventKey.new()
	rebuild()


## (Re)creates all actions. Call after changing bindings or the pad layout.
func rebuild() -> void:
	var pads := pad_devices()
	for p in [1, 2]:
		for a in ACTIONS:
			var action := "p%d_%s" % [p, a]
			if InputMap.has_action(action):
				InputMap.erase_action(action)
			InputMap.add_action(action, 0.25)
			for ev in _key_events(action):
				InputMap.action_add_event(action, ev)
			var dev: int = pads[p - 1]
			if dev >= 0:
				for ev in _pad_events(a, dev):
					InputMap.action_add_event(action, ev)
	if not InputMap.has_action("pause"):
		InputMap.add_action("pause")
		var esc := InputEventKey.new()
		esc.physical_keycode = KEY_ESCAPE
		InputMap.action_add_event("pause", esc)
		var start := InputEventJoypadButton.new()
		start.device = -1
		start.button_index = JOY_BUTTON_START
		InputMap.action_add_event("pause", start)


## Which joypad device each player uses. Layout 0: pad 0 -> P1, pad 1 -> P2.
## Layout 1: P1 keyboard only, pad 0 -> P2 (one pad, one keyboard).
func pad_devices() -> Array:
	var layout := int(SaveManager.get_setting("pad_layout", 0))
	if layout == 1:
		return [-1, 0]
	return [0, 1]


func _key_events(action: String) -> Array:
	var out: Array = []
	var custom: Dictionary = SaveManager.data["bindings"]
	var keys: Array = DEFAULT_KEYS[action]
	if custom.has(action):
		keys = [custom[action]]
	for k in keys:
		var code := int(k[0])
		var loc := int(k[1])
		if code == KEY_SHIFT or code == KEY_CTRL:
			# Without location support both Shift keys would fire both
			# players' handbrakes, so leave them out.
			if loc != 0 and not _location_supported:
				continue
		var ev := InputEventKey.new()
		ev.device = -1
		ev.physical_keycode = code
		if loc != 0 and _location_supported:
			ev.set("location", loc)
		out.append(ev)
	return out


func _pad_events(a: String, device: int) -> Array:
	var out: Array = []
	match a:
		"accel":
			out.append(_axis(device, JOY_AXIS_TRIGGER_RIGHT, 1.0))
			out.append(_button(device, JOY_BUTTON_A))
		"brake":
			out.append(_axis(device, JOY_AXIS_TRIGGER_LEFT, 1.0))
			out.append(_button(device, JOY_BUTTON_B))
		"left":
			out.append(_axis(device, JOY_AXIS_LEFT_X, -1.0))
			out.append(_button(device, JOY_BUTTON_DPAD_LEFT))
		"right":
			out.append(_axis(device, JOY_AXIS_LEFT_X, 1.0))
			out.append(_button(device, JOY_BUTTON_DPAD_RIGHT))
		"handbrake":
			out.append(_button(device, JOY_BUTTON_X))
			out.append(_button(device, JOY_BUTTON_RIGHT_SHOULDER))
		"reset":
			out.append(_button(device, JOY_BUTTON_Y))
	return out


func _axis(device: int, axis: JoyAxis, value: float) -> InputEventJoypadMotion:
	var e := InputEventJoypadMotion.new()
	e.device = device
	e.axis = axis
	e.axis_value = value
	return e


func _button(device: int, idx: JoyButton) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new()
	e.device = device
	e.button_index = idx
	return e


# --- remapping ------------------------------------------------------------

func rebind(action: String, ev: InputEventKey) -> void:
	var loc := 0
	if _location_supported:
		loc = int(ev.get("location"))
	var code := ev.physical_keycode if ev.physical_keycode != KEY_NONE else ev.keycode
	SaveManager.data["bindings"][action] = [int(code), loc]
	SaveManager.save_game()
	rebuild()


func reset_bindings() -> void:
	SaveManager.data["bindings"] = {}
	SaveManager.save_game()
	rebuild()


## Human readable list of the keyboard keys bound to an action.
func key_names(action: String) -> String:
	var names: PackedStringArray = []
	for ev in _key_events(action):
		var k := ev as InputEventKey
		var n := OS.get_keycode_string(k.physical_keycode)
		if _location_supported:
			var loc := int(k.get("location"))
			if loc == 1:
				n = "L " + n
			elif loc == 2:
				n = "R " + n
		names.append(n)
	return " / ".join(names)
