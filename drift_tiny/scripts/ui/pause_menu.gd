class_name PauseMenu
extends Control
## Pause overlay (Esc / Start). Works while the tree is paused.

signal restart_requested
signal quit_requested

var _box: VBoxContainer
var _first: Button
var can_pause := true


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	theme = UiTheme.get_theme()
	visible = false
	add_child(UiTheme.dimmer(0.65))
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := UiTheme.panel()
	center.add_child(panel)
	_box = VBoxContainer.new()
	_box.add_theme_constant_override("separation", 6)
	_box.custom_minimum_size = Vector2(300, 0)
	panel.add_child(_box)
	_box.add_child(UiTheme.label("PAUSED", 32, UiTheme.PINK))
	_first = UiTheme.button("Resume", close)
	_box.add_child(_first)
	_box.add_child(UiTheme.button("Restart race", func():
		close()
		restart_requested.emit()))
	_box.add_child(UiTheme.button("Quit to menu", func():
		close()
		quit_requested.emit()))
	var hint := UiTheme.label("P1: WASD + L-Shift   P2: Arrows + R-Shift   Reset: R / Backspace", 12, UiTheme.DIM)
	_box.add_child(hint)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		if visible:
			close()
		elif can_pause:
			open()
		get_viewport().set_input_as_handled()


func open() -> void:
	visible = true
	get_tree().paused = true
	_first.grab_focus()


func close() -> void:
	visible = false
	get_tree().paused = false
