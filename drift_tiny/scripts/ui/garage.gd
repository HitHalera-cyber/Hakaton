extends Control
## Garage: browse cars, unlock them, buy upgrades, paint, rims and decals,
## and choose which car 1P and 2P drive.

const PARTS := [
	["engine", "ENGINE", "Acceleration and top speed"],
	["tires", "TYRES", "Grip and steering"],
	["suspension", "SUSPENSION", "Drift control and stability"],
	["brakes", "BRAKES", "Braking power"],
]

var _car_id := "classic"
var _list: VBoxContainer
var _preview: Widgets.CarPreview
var _bars: Widgets.StatBars
var _name: Label
var _desc: Label
var _credits: Label
var _status: Label
var _parts_box: VBoxContainer
var _paint_box: HBoxContainer
var _rims: Widgets.OptionCycler
var _decal: Widgets.OptionCycler
var _actions: HBoxContainer


func _ready() -> void:
	theme = UiTheme.get_theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = UiTheme.BG
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var title := UiTheme.label("GARAGE", 34, UiTheme.PINK)
	title.position = Vector2(30, 18)
	add_child(title)
	_credits = UiTheme.label("", 22, UiTheme.CYAN)
	_credits.position = Vector2(780, 24)
	add_child(_credits)

	_list = VBoxContainer.new()
	_list.position = Vector2(30, 80)
	_list.add_theme_constant_override("separation", 2)
	add_child(_list)

	_preview = Widgets.CarPreview.new()
	_preview.position = Vector2(230, 70)
	_preview.size = Vector2(300, 220)
	add_child(_preview)
	_name = UiTheme.label("", 26, UiTheme.TEXT)
	_name.position = Vector2(240, 290)
	add_child(_name)
	_desc = UiTheme.label("", 14, UiTheme.DIM)
	_desc.position = Vector2(240, 324)
	_desc.size = Vector2(290, 40)
	_desc.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_desc)
	_bars = Widgets.StatBars.new()
	_bars.position = Vector2(240, 372)
	_bars.size = Vector2(290, 100)
	add_child(_bars)

	var right := VBoxContainer.new()
	right.position = Vector2(560, 80)
	right.custom_minimum_size = Vector2(380, 0)
	right.add_theme_constant_override("separation", 4)
	add_child(right)
	right.add_child(UiTheme.label("TUNING", 16, UiTheme.DIM))
	_parts_box = VBoxContainer.new()
	right.add_child(_parts_box)
	right.add_child(UiTheme.label("PAINT", 16, UiTheme.DIM))
	_paint_box = HBoxContainer.new()
	_paint_box.add_theme_constant_override("separation", 4)
	right.add_child(_paint_box)
	_rims = Widgets.OptionCycler.new("RIMS", Game.car_config.get("rims", ["Steel"]), range(Game.car_config.get("rims", ["Steel"]).size()))
	_rims.custom_minimum_size = Vector2(380, 32)
	_rims.changed.connect(_on_rims)
	right.add_child(_rims)
	_decal = Widgets.OptionCycler.new("DECAL", Game.car_config.get("decals", ["None"]), range(Game.car_config.get("decals", ["None"]).size()))
	_decal.custom_minimum_size = Vector2(380, 32)
	_decal.changed.connect(_on_decal)
	right.add_child(_decal)
	_status = UiTheme.label("", 15, UiTheme.CYAN)
	right.add_child(_status)

	_actions = HBoxContainer.new()
	_actions.position = Vector2(30, 484)
	_actions.add_theme_constant_override("separation", 10)
	add_child(_actions)

	_car_id = SaveManager.get_selected(1)
	_build_list()
	_select(_car_id)
	AudioManager.play_music("menu")


func _build_list() -> void:
	for c in _list.get_children():
		c.queue_free()
	for c in Game.cars:
		var id: String = c["id"]
		var label := str(c["name"])
		if not SaveManager.is_unlocked(id):
			label += "   %d CR" % int(c.get("price", 0))
		var tags := ""
		if SaveManager.get_selected(1) == id:
			tags += " 1P"
		if SaveManager.get_selected(2) == id:
			tags += " 2P"
		var b := UiTheme.button(label + tags, _select.bind(id), 18)
		b.custom_minimum_size = Vector2(185, 34)
		if not SaveManager.is_unlocked(id):
			b.add_theme_color_override("font_color", UiTheme.DIM)
		_list.add_child(b)
		b.focus_entered.connect(_select.bind(id))


func _select(id: String) -> void:
	_car_id = id
	_refresh()


func _refresh() -> void:
	var def := Game.car_def(_car_id)
	var unlocked := SaveManager.is_unlocked(_car_id)
	var st := SaveManager.car_state(_car_id)
	_credits.text = "%d CR" % SaveManager.get_currency()
	_name.text = str(def["name"]).to_upper() + ("" if unlocked else "  (LOCKED)")
	_desc.text = str(def.get("desc", ""))
	var stats := CarStats.build(_car_id)
	_preview.stats = stats
	_bars.set_bars(stats.bars(), CarStats.build(_car_id, false).bars())

	for c in _parts_box.get_children():
		c.queue_free()
	var max_lvl := CarStats.max_upgrade_level()
	for part in PARTS:
		var key: String = part[0]
		var lvl := int(st["upgrades"].get(key, 0))
		var pips := "["
		for i in max_lvl:
			pips += "#" if i < lvl else "-"
		pips += "]"
		var cost := CarStats.upgrade_cost(lvl)
		var txt := "%s  %s" % [str(part[1]).rpad(11), pips]
		if not unlocked:
			txt += "   locked"
		elif cost < 0:
			txt += "   MAX"
		else:
			txt += "   upgrade %d CR" % cost
		var b := UiTheme.button(txt, _buy_upgrade.bind(key), 17)
		b.tooltip_text = part[2]
		b.custom_minimum_size = Vector2(380, 32)
		b.disabled = not unlocked or cost < 0
		_parts_box.add_child(b)

	for c in _paint_box.get_children():
		c.queue_free()
	var colors: Array = Game.car_config.get("colors", [])
	var cur_color := int(st["color"])
	if cur_color < 0:
		cur_color = int(def.get("color", 0))
	for i in colors.size():
		var sw := Button.new()
		sw.custom_minimum_size = Vector2(32, 32)
		sw.focus_mode = Control.FOCUS_ALL
		var box := StyleBoxFlat.new()
		box.bg_color = Game.color_from_index(i)
		box.set_border_width_all(3 if i == cur_color else 1)
		box.border_color = UiTheme.PINK if i == cur_color else Color(0, 0, 0, 0.6)
		sw.add_theme_stylebox_override("normal", box)
		sw.add_theme_stylebox_override("hover", box)
		sw.add_theme_stylebox_override("pressed", box)
		var fbox := box.duplicate() as StyleBoxFlat
		fbox.border_color = Color.WHITE
		fbox.set_border_width_all(3)
		sw.add_theme_stylebox_override("focus", fbox)
		sw.disabled = not unlocked
		sw.pressed.connect(_paint.bind(i))
		_paint_box.add_child(sw)
	_rims.index = int(st["rims"])
	_rims._refresh()
	_decal.index = int(st["decal"])
	_decal._refresh()
	_rims.disabled = not unlocked
	_decal.disabled = not unlocked

	for c in _actions.get_children():
		c.queue_free()
	if unlocked:
		_actions.add_child(_action_button("USE FOR 1P", _use.bind(1)))
		_actions.add_child(_action_button("USE FOR 2P", _use.bind(2)))
	else:
		var price := int(def.get("price", 0))
		_actions.add_child(_action_button("UNLOCK %d CR" % price, _unlock))
	_actions.add_child(_action_button("BACK", Game.goto.bind("menu")))


func _action_button(text: String, cb: Callable) -> Button:
	var b := UiTheme.button(text, cb, 18)
	b.alignment = HORIZONTAL_ALIGNMENT_CENTER
	b.custom_minimum_size = Vector2(150, 40)
	return b


func _buy_upgrade(part: String) -> void:
	var st := SaveManager.car_state(_car_id)
	var lvl := int(st["upgrades"].get(part, 0))
	var cost := CarStats.upgrade_cost(lvl)
	if cost < 0:
		return
	if not SaveManager.spend(cost):
		_status.text = "Not enough credits — race to earn more."
		AudioManager.play("ui_error")
		return
	st["upgrades"][part] = lvl + 1
	SaveManager.save_game()
	_status.text = "%s upgraded to level %d" % [part.capitalize(), lvl + 1]
	AudioManager.play("reward")
	_refresh_keep_focus()


func _paint(i: int) -> void:
	SaveManager.car_state(_car_id)["color"] = i
	SaveManager.save_game()
	_refresh_keep_focus()


func _on_rims(v: Variant) -> void:
	SaveManager.car_state(_car_id)["rims"] = int(v)
	SaveManager.save_game()
	_preview.stats = CarStats.build(_car_id)


func _on_decal(v: Variant) -> void:
	SaveManager.car_state(_car_id)["decal"] = int(v)
	SaveManager.save_game()
	_preview.stats = CarStats.build(_car_id)


func _unlock() -> void:
	var price := int(Game.car_def(_car_id).get("price", 0))
	if not SaveManager.spend(price):
		_status.text = "Need %d CR to unlock." % price
		AudioManager.play("ui_error")
		return
	SaveManager.unlock_car(_car_id)
	AudioManager.play("unlock")
	_status.text = "%s unlocked!" % Game.car_def(_car_id)["name"]
	if SaveManager.data["unlocked"].size() >= Game.cars.size():
		SaveManager.unlock_achievement("collector")
	_build_list()
	_refresh()


func _use(player: int) -> void:
	SaveManager.set_selected(player, _car_id)
	_status.text = "%dP drives the %s" % [player, Game.car_def(_car_id)["name"]]
	_build_list()


## Rebuilding the buttons drops focus; put it back on the same row.
func _refresh_keep_focus() -> void:
	var focused := get_viewport().gui_get_focus_owner()
	var path := ""
	var idx := -1
	if focused and focused.get_parent() in [_parts_box, _paint_box]:
		path = "parts" if focused.get_parent() == _parts_box else "paint"
		idx = focused.get_index()
	_refresh()
	if idx >= 0:
		await get_tree().process_frame
		var box: Node = _parts_box if path == "parts" else _paint_box
		if idx < box.get_child_count():
			(box.get_child(idx) as Control).grab_focus()
