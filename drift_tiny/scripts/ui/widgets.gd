class_name Widgets
extends RefCounted
## Small reusable menu widgets (inner classes so they share one file).


## A focusable button that cycles through options with Left/Right or a click:
## "MODE        < Time Attack >". Works the same with keyboard and gamepad.
class OptionCycler:
	extends Button

	signal changed(value: Variant)

	var title := ""
	var labels: Array = []
	var values: Array = []
	var index := 0

	func _init(t: String, option_labels: Array, option_values: Array, start := 0) -> void:
		title = t
		labels = option_labels
		values = option_values
		index = clampi(start, 0, maxi(labels.size() - 1, 0))
		focus_mode = Control.FOCUS_ALL
		alignment = HORIZONTAL_ALIGNMENT_LEFT
		add_theme_font_size_override("font_size", 18)
		custom_minimum_size = Vector2(420, 34)
		pressed.connect(func(): step(1))
		focus_entered.connect(func(): AudioManager.play("ui_move", 1.0, -8.0))
		_refresh()

	func set_options(option_labels: Array, option_values: Array, keep_value: Variant = null) -> void:
		labels = option_labels
		values = option_values
		var i := values.find(keep_value)
		index = i if i >= 0 else 0
		_refresh()

	func value() -> Variant:
		return values[index] if index < values.size() else null

	func step(d: int) -> void:
		if labels.size() <= 1:
			return
		index = posmod(index + d, labels.size())
		AudioManager.play("ui_move")
		_refresh()
		changed.emit(value())

	func _gui_input(event: InputEvent) -> void:
		if event.is_action_pressed("ui_left"):
			step(-1)
			accept_event()
		elif event.is_action_pressed("ui_right"):
			step(1)
			accept_event()

	func _refresh() -> void:
		var v := str(labels[index]) if index < labels.size() else "-"
		text = "%s   <  %s  >" % [title.rpad(14), v]


## Large rotating car for the garage and setup screens.
class CarPreview:
	extends Control

	var stats: CarStats
	var zoom := 7.0
	var spin := true
	var angle := -0.6

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if spin:
			angle += delta * 0.6
		queue_redraw()

	func _draw() -> void:
		if stats == null:
			return
		var c := size * 0.5
		# Turntable.
		draw_circle(c + Vector2(0, 4), minf(size.x, size.y) * 0.42, Color(0.0, 0.0, 0.0, 0.3))
		draw_circle(c, minf(size.x, size.y) * 0.42, Color("1c1838"))
		draw_arc(c, minf(size.x, size.y) * 0.42, 0.0, TAU, 64, Color("3b2d6b"), 3.0)
		var base := Transform2D(angle, Vector2(zoom, zoom), 0.0, c)
		var shadow := Transform2D(angle, Vector2(zoom, zoom), 0.0, c + Vector2(6, 9))
		CarPainter.draw_shadow(self, shadow, stats.length, stats.width)
		CarPainter.draw_car(self, base, stats.shape, stats.length, stats.width, stats.color, stats.rims, stats.decal)


## Horizontal stat bars, optionally with a "before upgrade" ghost bar.
class StatBars:
	extends Control

	var bars: Dictionary = {}
	var compare: Dictionary = {}

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		custom_minimum_size = Vector2(300, 100)

	func set_bars(b: Dictionary, cmp: Dictionary = {}) -> void:
		bars = b
		compare = cmp
		queue_redraw()

	func _draw() -> void:
		var font := ThemeDB.fallback_font
		var y := 4.0
		for key in bars.keys():
			draw_string(font, Vector2(0, y + 13), str(key).to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, UiTheme.DIM)
			var w := size.x - 90.0
			var x := 86.0
			draw_rect(Rect2(x, y + 2, w, 12), Color("241f45"))
			var v: float = bars[key]
			if compare.has(key):
				var old: float = compare[key]
				draw_rect(Rect2(x, y + 2, w * old, 12), Color(UiTheme.CYAN, 0.6))
			var segs := 12
			for i in segs:
				if float(i) / segs < v:
					var col := UiTheme.PINK.lerp(UiTheme.PURPLE, float(i) / segs)
					draw_rect(Rect2(x + i * (w / segs) + 1, y + 3, w / segs - 2, 10), col)
			y += 22.0


## Track outline thumbnail in the track's colours.
class TrackPreview:
	extends Control

	var data: TrackData

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func set_track(d: TrackData) -> void:
		data = d
		queue_redraw()

	func _draw() -> void:
		var bg := Color("17142e")
		var road := Color("5a5568")
		var accent := UiTheme.PINK
		if data:
			var th: Dictionary = Track.THEMES.get(data.theme, {})
			bg = Color.html(th.get("ground", "17142e")).darkened(0.35)
			road = Color.html(th.get("road", "5a5568")).lightened(0.25)
			accent = Color.html(th.get("curb_a", "ff5fb8"))
		draw_rect(Rect2(Vector2.ZERO, size), bg)
		draw_rect(Rect2(Vector2.ZERO, size), Color("3b2d6b"), false, 2.0)
		if data == null:
			return
		var b := Rect2(data.samples[0], Vector2.ZERO)
		for p in data.samples:
			b = b.expand(p)
		var pad := 16.0
		var s := minf((size.x - pad * 2) / b.size.x, (size.y - pad * 2) / b.size.y)
		var off := (size - b.size * s) * 0.5 - b.position * s
		var pts := PackedVector2Array()
		for i in range(0, data.size(), 3):
			pts.append(data.samples[i] * s + off)
		pts.append(pts[0])
		draw_polyline(pts, Color(0, 0, 0, 0.4), 9.0)
		draw_polyline(pts, road, 6.0)
		draw_polyline(pts, Color(1, 1, 1, 0.35), 1.0)
		var start := data.samples[0] * s + off
		draw_rect(Rect2(start - Vector2(4, 4), Vector2(8, 8)), accent)
		# Direction arrow at the start.
		var t := data.tangents[0]
		draw_line(start, start + t * 18.0, Color.WHITE, 2.0)


## "DRIFT TINY" logo, drawn with the UI font plus a checker flag.
class Logo:
	extends Control

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		custom_minimum_size = Vector2(300, 150)

	func _draw() -> void:
		var font := ThemeDB.fallback_font
		var t := Time.get_ticks_msec() / 1000.0
		# Speed streaks behind the letters.
		for i in 6:
			var y := 30.0 + i * 11.0
			var w := 60.0 + 30.0 * sin(t * 2.0 + i)
			draw_rect(Rect2(-10, y, w, 3), Color(UiTheme.PINK, 0.35 - i * 0.04))
		draw_string_outline(font, Vector2(8, 70), "DRIFT", HORIZONTAL_ALIGNMENT_LEFT, -1, 72, 10, Color("2a1050"))
		draw_string(font, Vector2(8, 70), "DRIFT", HORIZONTAL_ALIGNMENT_LEFT, -1, 72, Color("f4ecff"))
		draw_string_outline(font, Vector2(92, 128), "TINY", HORIZONTAL_ALIGNMENT_LEFT, -1, 64, 10, Color("2a1050"))
		draw_string(font, Vector2(92, 128), "TINY", HORIZONTAL_ALIGNMENT_LEFT, -1, 64, UiTheme.PINK)
		# Checker flag.
		for r in 3:
			for c in 6:
				var col := Color.WHITE if (r + c) % 2 == 0 else Color("141418")
				draw_rect(Rect2(14 + c * 11, 84 + r * 11, 11, 11), col)
		draw_string(font, Vector2(16, 148), "SMALL CARS. BIG DRIFT.", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("f4ecff"))

	func _process(_d: float) -> void:
		queue_redraw()
