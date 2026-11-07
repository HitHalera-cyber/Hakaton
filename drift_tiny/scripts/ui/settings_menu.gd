extends Control
## Settings: language, display and graphics, audio volumes, two-player options
## and key remapping.

var _waiting_action := ""
var _bind_buttons: Dictionary = {}
var _info: Label


func _ready() -> void:
	theme = UiTheme.get_theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = UiTheme.BG
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var title := UiTheme.label("SETTINGS", 34, UiTheme.PINK)
	title.position = Vector2(30, 18)
	add_child(title)

	var scroll := ScrollContainer.new()
	scroll.position = Vector2(30, 72)
	scroll.size = Vector2(900, 410)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	add_child(scroll)
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 40)
	scroll.add_child(cols)
	var left := VBoxContainer.new()
	left.add_theme_constant_override("separation", 4)
	cols.add_child(left)
	var right := VBoxContainer.new()
	right.add_theme_constant_override("separation", 2)
	cols.add_child(right)

	var codes: Array = Lang.NAMES.keys()
	var lang := Widgets.OptionCycler.new("LANGUAGE", Lang.NAMES.values(), codes, codes.find(Lang.current()))
	lang.custom_minimum_size = Vector2(400, 32)
	lang.changed.connect(_on_language)
	left.add_child(lang)
	left.add_child(UiTheme.label("DISPLAY", 16, UiTheme.DIM))
	left.add_child(_toggle("Fullscreen", "fullscreen", func(on): Game.set_fullscreen(on)))
	left.add_child(_toggle("VSync", "vsync", func(on): Game.set_vsync(on)))
	left.add_child(_toggle("Pixel-perfect (integer) scaling", "integer_scaling", func(on): Game.set_integer_scaling(on)))
	left.add_child(_toggle("Show FPS", "show_fps", func(on): Game.set_show_fps(on)))
	left.add_child(UiTheme.label("GRAPHICS", 16, UiTheme.DIM))
	var quality := Widgets.OptionCycler.new("QUALITY", ["Low", "Medium", "High"], [0, 1, 2],
			int(SaveManager.get_setting("quality", 2)))
	quality.custom_minimum_size = Vector2(400, 32)
	quality.changed.connect(func(v): SaveManager.set_setting("quality", int(v)))
	left.add_child(quality)
	var sids: Array = GraphicsStyle.ORDER
	var snames: Array = []
	for sid in sids:
		snames.append(GraphicsStyle.STYLES[sid]["name"])
	var style := Widgets.OptionCycler.new("STYLE", snames, sids, sids.find(GraphicsStyle.current_id()))
	style.custom_minimum_size = Vector2(400, 32)
	style.changed.connect(func(v): SaveManager.set_setting("style", str(v)))
	left.add_child(style)
	var qhint := UiTheme.label("Low quality turns off weather and glow and thins out smoke — for older PCs.", 12, UiTheme.DIM)
	qhint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	qhint.custom_minimum_size = Vector2(400, 0)
	left.add_child(qhint)
	left.add_child(UiTheme.label("AUDIO", 16, UiTheme.DIM))
	left.add_child(_slider("Master", "master_volume"))
	left.add_child(_slider("Music", "music_volume"))
	left.add_child(_slider("Engine", "engine_volume"))
	left.add_child(_slider("Effects", "sfx_volume"))
	left.add_child(UiTheme.label("GAMEPLAY", 16, UiTheme.DIM))
	var view := Widgets.OptionCycler.new("2P SCREEN", ["Split screen", "Shared camera"], ["split", "shared"],
			0 if str(SaveManager.get_setting("two_player_view", "split")) == "split" else 1)
	view.custom_minimum_size = Vector2(400, 32)
	view.changed.connect(func(v):
		SaveManager.set_setting("two_player_view", v)
		Game.view_mode = v)
	left.add_child(view)
	var pads := Widgets.OptionCycler.new("GAMEPADS", ["Pad 1 > 1P, Pad 2 > 2P", "Keyboard 1P, Pad 1 > 2P"], [0, 1],
			int(SaveManager.get_setting("pad_layout", 0)))
	pads.custom_minimum_size = Vector2(400, 32)
	pads.changed.connect(func(v):
		SaveManager.set_setting("pad_layout", v)
		InputSetup.rebuild())
	left.add_child(pads)
	left.add_child(_toggle("Camera shake", "camera_shake", func(_on): pass))
	left.add_child(_toggle("Changing weather and time of day", "dynamic_weather", func(_on): pass))
	left.add_child(_toggle("Best drift replay after the race", "replays", func(_on): pass))

	var ctl := UiTheme.label("CONTROLS (keyboard) — select and press a key", 16, UiTheme.DIM)
	ctl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ctl.custom_minimum_size = Vector2(400, 0)
	right.add_child(ctl)
	for p in [1, 2]:
		right.add_child(UiTheme.label(tr("PLAYER %d") % p, 15, UiTheme.PINK if p == 1 else UiTheme.CYAN))
		for a in InputSetup.ACTIONS:
			var action := "p%d_%s" % [p, a]
			var b := UiTheme.button("", _start_rebind.bind(action), 15)
			b.custom_minimum_size = Vector2(400, 26)
			right.add_child(b)
			_bind_buttons[action] = b
	right.add_child(UiTheme.button("Reset controls to default", _reset_controls, 15))
	right.add_child(UiTheme.label("Gamepads: RT/A gas · LT/B brake · stick steer · X/RB handbrake · Y reset", 12, UiTheme.DIM))
	_refresh_bindings()

	_info = UiTheme.label("", 14, UiTheme.CYAN)
	_info.position = Vector2(220, 496)
	add_child(_info)
	var back := UiTheme.button("BACK", _on_back, 20)
	back.alignment = HORIZONTAL_ALIGNMENT_CENTER
	back.custom_minimum_size = Vector2(160, 40)
	back.position = Vector2(30, 488)
	add_child(back)
	(left.get_child(0) as Control).grab_focus()


func _on_language(code: Variant) -> void:
	Lang.set_language(str(code))
	# Rebuild the screen so every label picks up the new language.
	Game.goto("settings")


func _toggle(text: String, key: String, apply: Callable) -> CheckButton:
	var c := CheckButton.new()
	c.text = text
	c.button_pressed = bool(SaveManager.get_setting(key, false))
	c.focus_mode = Control.FOCUS_ALL
	c.add_theme_font_size_override("font_size", 17)
	c.toggled.connect(func(on: bool):
		SaveManager.set_setting(key, on)
		apply.call(on)
		AudioManager.play("ui_select"))
	return c


func _slider(text: String, key: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	var l := UiTheme.label(text, 17)
	l.custom_minimum_size = Vector2(110, 0)
	row.add_child(l)
	var s := HSlider.new()
	s.min_value = 0.0
	s.max_value = 1.0
	s.step = 0.05
	s.value = float(SaveManager.get_setting(key, 0.8))
	s.custom_minimum_size = Vector2(260, 24)
	s.focus_mode = Control.FOCUS_ALL
	s.value_changed.connect(func(v: float):
		SaveManager.data["settings"][key] = v
		AudioManager.apply_volumes())
	s.drag_ended.connect(func(_changed: bool): SaveManager.save_game())
	s.focus_exited.connect(SaveManager.save_game)
	row.add_child(s)
	return row


func _refresh_bindings() -> void:
	for action in _bind_buttons.keys():
		var a: String = action
		var short := a.substr(3)
		var b: Button = _bind_buttons[a]
		var keys := InputSetup.key_names(a) if a != _waiting_action else tr("press a key...  (Esc cancels)")
		b.text = "%s   %s" % [tr(str(InputSetup.ACTION_LABELS[short])).rpad(18), keys]


func _start_rebind(action: String) -> void:
	_waiting_action = action
	_info.text = tr("Press the new key for %s") % action.to_upper()
	_refresh_bindings()


func _input(event: InputEvent) -> void:
	if _waiting_action == "":
		return
	if event is InputEventKey and event.pressed and not event.echo:
		get_viewport().set_input_as_handled()
		var k := event as InputEventKey
		if k.physical_keycode == KEY_ESCAPE:
			_info.text = tr("Cancelled")
		else:
			InputSetup.rebind(_waiting_action, k)
			_info.text = "%s = %s" % [_waiting_action.to_upper(), InputSetup.key_names(_waiting_action)]
			AudioManager.play("ui_select")
		var b: Button = _bind_buttons[_waiting_action]
		_waiting_action = ""
		_refresh_bindings()
		b.grab_focus()


func _reset_controls() -> void:
	InputSetup.reset_bindings()
	_info.text = tr("Controls reset")
	_refresh_bindings()


func _on_back() -> void:
	SaveManager.save_game()
	Game.goto("menu")


func _unhandled_input(event: InputEvent) -> void:
	if _waiting_action == "" and event.is_action_pressed("ui_cancel"):
		_on_back()
