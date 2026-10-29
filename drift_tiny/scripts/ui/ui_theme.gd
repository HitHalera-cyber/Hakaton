class_name UiTheme
extends RefCounted
## Shared menu look (dark navy panels, pink/purple neon accents) built in code,
## plus small helpers for building menus quickly.

const BG := Color("0d0b1f")
const PANEL := Color("17142e")
const PANEL_EDGE := Color("3b2d6b")
const PINK := Color("ff5fb8")
const PURPLE := Color("9a4ef0")
const CYAN := Color("3ee0ff")
const TEXT := Color("ece8ff")
const DIM := Color("9a93c0")

static var _theme: Theme


static func get_theme() -> Theme:
	if _theme != null:
		return _theme
	var t := Theme.new()
	t.default_font_size = 18
	var normal := _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0)
	var hover := _box(Color(0.6, 0.3, 0.95, 0.25), PURPLE, 0)
	var focus := _box(Color(0.6, 0.25, 0.9, 0.85), PINK, 2)
	var pressed := _box(PINK, PINK, 2)
	var disabled := _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0)
	t.set_stylebox("normal", "Button", normal)
	t.set_stylebox("hover", "Button", hover)
	t.set_stylebox("pressed", "Button", pressed)
	t.set_stylebox("focus", "Button", focus)
	t.set_stylebox("disabled", "Button", disabled)
	t.set_color("font_color", "Button", TEXT)
	t.set_color("font_hover_color", "Button", Color.WHITE)
	t.set_color("font_focus_color", "Button", Color.WHITE)
	t.set_color("font_pressed_color", "Button", Color.WHITE)
	t.set_color("font_disabled_color", "Button", Color(DIM, 0.6))
	t.set_constant("outline_size", "Button", 0)
	t.set_color("font_color", "Label", TEXT)
	var panel := _box(Color(PANEL, 0.92), PANEL_EDGE, 2)
	panel.content_margin_left = 16
	panel.content_margin_right = 16
	panel.content_margin_top = 12
	panel.content_margin_bottom = 12
	t.set_stylebox("panel", "PanelContainer", panel)
	t.set_stylebox("panel", "Panel", panel)
	# Sliders
	var track_box := _box(Color("2a2450"), Color("2a2450"), 0)
	track_box.content_margin_top = 3
	track_box.content_margin_bottom = 3
	t.set_stylebox("slider", "HSlider", track_box)
	t.set_stylebox("grabber_area", "HSlider", _box(PURPLE, PURPLE, 0))
	t.set_stylebox("grabber_area_highlight", "HSlider", _box(PINK, PINK, 0))
	t.set_stylebox("focus", "HSlider", _box(Color(0, 0, 0, 0), PINK, 2))
	# Check buttons
	t.set_color("font_color", "CheckButton", TEXT)
	t.set_stylebox("focus", "CheckButton", focus)
	t.set_stylebox("hover", "CheckButton", hover)
	t.set_stylebox("normal", "CheckButton", normal)
	t.set_stylebox("pressed", "CheckButton", normal)
	# Scroll
	t.set_stylebox("panel", "ScrollContainer", _box(Color(0, 0, 0, 0), Color(0, 0, 0, 0), 0))
	_theme = t
	return t


static func _box(bg: Color, edge: Color, border: int) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = edge
	s.set_border_width_all(border)
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 4
	s.content_margin_bottom = 4
	s.anti_aliasing = false
	return s


static func label(text: String, size := 18, color := TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


static func button(text: String, cb: Callable, size := 20) -> Button:
	var b := Button.new()
	b.text = text
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.add_theme_font_size_override("font_size", size)
	b.focus_mode = Control.FOCUS_ALL
	b.pressed.connect(func():
		AudioManager.play("ui_select")
		cb.call())
	b.focus_entered.connect(func(): AudioManager.play("ui_move", 1.0, -8.0))
	return b


static func panel() -> PanelContainer:
	return PanelContainer.new()


## Makes a full-screen dimmed backdrop control.
static func dimmer(alpha := 0.6) -> ColorRect:
	var c := ColorRect.new()
	c.color = Color(0.02, 0.01, 0.06, alpha)
	c.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	c.mouse_filter = Control.MOUSE_FILTER_STOP
	return c
