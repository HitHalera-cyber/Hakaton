extends Control
## Title screen: logo, menu, live drifting backdrop.

var _menu: VBoxContainer
var _credits: Label
var _toast: Label
var _toast_t := 0.0


func _ready() -> void:
	theme = UiTheme.get_theme()
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var backdrop := MenuBackdrop.new()
	backdrop.track_id = "mountain"
	backdrop.car_id = SaveManager.get_selected(1)
	add_child(backdrop)

	var logo := Widgets.Logo.new()
	logo.position = Vector2(40, 34)
	add_child(logo)

	_menu = VBoxContainer.new()
	_menu.position = Vector2(48, 214)
	_menu.custom_minimum_size = Vector2(280, 0)
	_menu.add_theme_constant_override("separation", 2)
	add_child(_menu)
	var items := [
		["PLAY", _on_play],
		["LOCAL MULTIPLAYER", _on_multiplayer],
		["GARAGE", Game.goto.bind("garage")],
		["TRACKS", _on_tracks],
		["RECORDS", Game.goto.bind("records")],
		["SETTINGS", Game.goto.bind("settings")],
		["QUIT", _on_quit],
	]
	for it in items:
		var b := UiTheme.button(it[0], it[1], 22)
		b.custom_minimum_size = Vector2(280, 36)
		_menu.add_child(b)

	_credits = UiTheme.label("", 18, UiTheme.CYAN)
	_credits.position = Vector2(48, 486)
	add_child(_credits)
	var hint := UiTheme.label("Enter / A — select     Esc / Start — pause in race     v0.1", 12, UiTheme.DIM)
	hint.position = Vector2(48, 512)
	add_child(hint)
	_toast = UiTheme.label("", 16, UiTheme.PINK)
	_toast.position = Vector2(560, 500)
	_toast.visible = false
	add_child(_toast)

	_refresh_credits()
	SaveManager.currency_changed.connect(_on_currency)
	SaveManager.achievement_unlocked.connect(_on_achievement)
	AudioManager.play_music("menu")
	(_menu.get_child(0) as Button).grab_focus()


func _on_currency(_value: int) -> void:
	_refresh_credits()


func _refresh_credits() -> void:
	_credits.text = "%d CR" % SaveManager.get_currency()


func _on_achievement(_id: String, title: String) -> void:
	_toast.text = "Achievement: " + title
	_toast.visible = true
	_toast_t = 4.0


func _process(delta: float) -> void:
	if _toast_t > 0.0:
		_toast_t -= delta
		if _toast_t <= 0.0:
			_toast.visible = false


func _on_play() -> void:
	Game.players = 1
	if not (Game.mode in Game.modes_for(1)):
		Game.mode = "time_attack"
	Game.goto("setup")


func _on_multiplayer() -> void:
	Game.players = 2
	if not (Game.mode in Game.modes_for(2)):
		Game.mode = "versus"
	Game.goto("setup")


func _on_tracks() -> void:
	Game.set_meta("focus_track", true)
	Game.goto("setup")


func _on_quit() -> void:
	SaveManager.save_game()
	get_tree().quit()
