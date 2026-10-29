class_name RaceHUD
extends Control
## Heads-up display of one player's view: score + combo, timer, lap, position,
## minimap, speed and drift popups. Drawn with draw calls at the UI
## resolution (960x540) on top of the low-res game view.

const PINK := Color("ff5fb8")
const PURPLE := Color("9a4ef0")
const PANEL := Color(0.05, 0.04, 0.12, 0.72)
const EDGE := Color(0.6, 0.35, 0.95, 0.9)
const WHITE := Color("f4f0ff")

var car: Car
var race: Node            # RaceManager
var rival_cars: Array = []
var all_cars: Array = []
var ghost: Node2D
var track: TrackData
var compact := false      # split screen: narrower layout
var show_race_info := true  # timer, minimap, lap (off for the 2nd HUD of a shared screen)

var _font: Font
var _popups: Array = []   # {text, pts, kind, t}
var _message := ""
var _message_color := WHITE
var _message_t := 0.0
var _message_big := true
var _map_cache := PackedVector2Array()
var _map_rect := Rect2()


func _ready() -> void:
	_font = ThemeDB.fallback_font
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)


func bind(the_car: Car, the_race: Node, cars: Array, track_data: TrackData) -> void:
	car = the_car
	race = the_race
	all_cars = cars
	track = track_data
	rival_cars = []
	for c in cars:
		if c != car and (c as Car).player_index > 0:
			rival_cars.append(c)
	car.scoring.popup.connect(_on_popup)


func _on_popup(text: String, pts: int, kind: String) -> void:
	_popups.push_front({"text": text, "pts": pts, "kind": kind, "t": 0.0})
	if _popups.size() > 4:
		_popups.pop_back()
	AudioManager.play("drift_bank" if kind == "bank" else "drift_fail", 1.0 if kind == "bank" else 0.9, -4.0)


func show_message(text: String, col := WHITE, duration := 1.2, big := true) -> void:
	_message = text
	_message_color = col
	_message_t = duration
	_message_big = big


func _process(delta: float) -> void:
	for p in _popups:
		p["t"] = float(p["t"]) + delta
	while not _popups.is_empty() and float(_popups[-1]["t"]) > 2.2:
		_popups.pop_back()
	if _message_t > 0.0:
		_message_t -= delta
	queue_redraw()


func _draw() -> void:
	if car == null or race == null:
		return
	var w := size.x
	var h := size.y
	var info: Dictionary = race.racer_info(car)
	var col: Color = car.tag_color

	# --- score panel (top-left)
	var sp := Rect2(10, 10, 150 if compact else 230, 58 if rival_cars.is_empty() else 84)
	_panel(sp, col)
	_text(Vector2(sp.position.x + 10, sp.position.y + 30), "%dP" % maxi(car.player_index, 1), 24, col)
	_text(Vector2(sp.position.x + 52, sp.position.y + 30), _fmt_points(car.scoring.total), 24, WHITE)
	if car.scoring.in_chain:
		_text(Vector2(sp.end.x - 46, sp.position.y + 30), "x%.1f" % car.scoring.multiplier, 16, PINK)
	_text(Vector2(sp.position.x + 52, sp.position.y + 50), ("COMBO %s" if compact else "BEST COMBO %s") % _fmt_points(car.scoring.best_combo), 12, Color(WHITE, 0.6))
	var ry := sp.position.y + 74
	for r in rival_cars:
		var rc := r as Car
		_text(Vector2(sp.position.x + 10, ry), "%dP" % rc.player_index, 14, rc.tag_color)
		_text(Vector2(sp.position.x + 52, ry), _fmt_points(rc.scoring.total), 14, Color(WHITE, 0.8))
		ry += 16

	_draw_race_info(w, info)
	_draw_bottom(w, h)


func _draw_race_info(w: float, info: Dictionary) -> void:
	if not show_race_info:
		return
	# --- timer (top-centre)
	var t: float = race.elapsed_for(car)
	var tw := 116.0 if compact else 150.0
	var tr := Rect2(w * 0.5 - tw * 0.5 + (14.0 if compact else 0.0), 10, tw, 40)
	_panel(tr, EDGE)
	_text_c(Vector2(tr.get_center().x, tr.position.y + 28), format_time(t), 20 if compact else 24, WHITE)
	var sub := ""
	if float(info.get("last_lap", 0.0)) > 0.0:
		sub = "LAST %s" % format_time(info["last_lap"])
	if float(info.get("best_lap", 0.0)) > 0.0:
		sub += "   BEST %s" % format_time(info["best_lap"])
	if sub != "":
		_text_c(Vector2(tr.get_center().x, tr.end.y + 16), sub, 12, Color(WHITE, 0.75))
	var mode_line: String = race.mode_line(car)
	if mode_line != "":
		_text_c(Vector2(tr.get_center().x, tr.end.y + (32 if sub != "" else 16)), mode_line, 14, PINK)

	# --- minimap + lap + position (top-right)
	var mw := 104.0 if compact else 130.0
	var mr := Rect2(w - mw - 10, 10, mw, mw * 0.72)
	_panel(mr, EDGE)
	_draw_minimap(mr.grow(-6))
	var lr := Rect2(mr.position.x, mr.end.y + 4, mw, 30)
	_panel(lr, EDGE)
	var laps_total: int = info.get("laps_total", 0)
	var lap_text := "LAP %d/%d" % [mini(int(info.get("lap", 1)), laps_total), laps_total] if laps_total > 0 else "LAP %d" % int(info.get("lap", 1))
	_text_c(Vector2(lr.get_center().x, lr.position.y + 22), lap_text, 18, WHITE)
	var pos: int = info.get("position", 0)
	if pos > 0 and int(info.get("racers", 1)) > 1:
		_text_c(Vector2(lr.get_center().x, lr.end.y + 30), _ordinal(pos), 26, PINK if pos == 1 else WHITE)


func _draw_bottom(w: float, h: float) -> void:
	var info: Dictionary = race.racer_info(car)
	# --- speed (bottom-left)
	var kr := Rect2(10, h - 58, 170 if compact else 200, 48)
	_panel(kr, EDGE)
	_text(Vector2(kr.position.x + 12, kr.position.y + 32), "%d" % car.kmh(), 28, WHITE)
	_text(Vector2(kr.position.x + 72, kr.position.y + 32), "KM/H", 12, Color(WHITE, 0.7))
	var segs := 5 if compact else 8
	var fill := int(round(clampf(car.speed / car.stats.max_speed, 0.0, 1.0) * segs))
	for i in segs:
		var c := PINK.lerp(PURPLE, float(i) / segs) if i < fill else Color(1, 1, 1, 0.12)
		draw_rect(Rect2(kr.position.x + (116 if compact else 122) + i * 9, kr.position.y + 18, 7, 14), c)
	if not car.on_road:
		_text(Vector2(kr.position.x, kr.position.y - 8), "OFF ROAD", 12, Color("ffb347"))
	elif car.surface_name == "ice":
		_text(Vector2(kr.position.x, kr.position.y - 8), "ICE!", 12, Color("bfe6ff"))

	# --- current drift (bottom-right)
	if car.scoring.in_chain:
		var dr := Rect2(w - (190 if compact else 230), h - 66, 180 if compact else 220, 56)
		_panel(dr, PINK)
		_text(Vector2(dr.position.x + 12, dr.position.y + 26), "DRIFT", 20, PINK)
		_text(Vector2(dr.position.x + 84, dr.position.y + 26), "+%s" % _fmt_points(car.scoring.shown_points()), 20, WHITE)
		_text(Vector2(dr.position.x + 12, dr.position.y + 46), "x%.1f" % car.scoring.multiplier, 16, WHITE)
		if car.scoring.proximity:
			_text(Vector2(dr.position.x + 64, dr.position.y + 46), "CLOSE!", 12, Color("ffd84a"))
		if car.scoring.tandem:
			_text(Vector2(dr.position.x + 120, dr.position.y + 46), "TANDEM", 12, Color("3ee0ff"))
		var k := car.scoring.chain_timer / DriftScoring.CHAIN_WINDOW
		draw_rect(Rect2(dr.position.x, dr.end.y - 3, dr.size.x * k, 3), PINK)

	# --- popups (right side, stacked)
	var py := h - 90.0
	for p in _popups:
		var age: float = p["t"]
		var a := clampf(2.2 - age, 0.0, 1.0)
		var kind: String = p["kind"]
		var pc := Color("ffd84a") if kind == "bank" else Color("ff5a5a")
		if str(p["text"]).begins_with("PERFECT"):
			pc = Color("3ee0ff")
		var line := "%s  %s%s" % [p["text"], "+" if kind == "bank" else "-", _fmt_points(p["pts"])]
		_text_r(Vector2(w - 14, py - age * 14.0), line, 16, Color(pc, a))
		py -= 22.0

	# --- centre messages
	if _message_t > 0.0 and _message != "":
		var a := clampf(_message_t * 3.0, 0.0, 1.0)
		var fs := 56 if _message_big else 24
		_text_c(Vector2(w * 0.5, h * 0.42), _message, fs, Color(_message_color, a), 6)
	if info.get("wrong_way", false):
		_text_c(Vector2(w * 0.5, h * 0.3), "WRONG WAY", 30, Color("ff5a5a"), 4)
	if info.get("finished", false) and not race.is_over():
		_text_c(Vector2(w * 0.5, h * 0.55), "FINISHED — waiting for others", 18, WHITE, 3)


func _draw_minimap(r: Rect2) -> void:
	if track == null:
		return
	if _map_cache.is_empty() or _map_rect != r:
		_map_rect = r
		_map_cache = PackedVector2Array()
		var b := Rect2(track.samples[0], Vector2.ZERO)
		for p in track.samples:
			b = b.expand(p)
		var s := minf(r.size.x / b.size.x, r.size.y / b.size.y)
		var off := r.position + (r.size - b.size * s) * 0.5 - b.position * s
		for i in range(0, track.size(), 4):
			_map_cache.append(track.samples[i] * s + off)
		_map_cache.append(_map_cache[0])
		set_meta("map_scale", s)
		set_meta("map_off", off)
	draw_polyline(_map_cache, Color(1, 1, 1, 0.25), 5.0)
	draw_polyline(_map_cache, Color(0.85, 0.85, 1.0, 0.85), 2.0)
	var s: float = get_meta("map_scale")
	var off: Vector2 = get_meta("map_off")
	draw_rect(Rect2(_map_cache[0] - Vector2(2, 2), Vector2(4, 4)), Color.WHITE)
	if ghost and ghost.visible:
		draw_circle(ghost.global_position * s + off, 2.5, Color(0.75, 0.85, 1.0, 0.7))
	for c in all_cars:
		var cc := c as Car
		if cc == car:
			continue
		var dc := cc.tag_color if cc.player_index > 0 else Color(0.8, 0.8, 0.85)
		draw_circle(cc.global_position * s + off, 2.5, dc)
	draw_circle(car.global_position * s + off, 3.5, Color.BLACK)
	draw_circle(car.global_position * s + off, 2.5, car.tag_color)


# --- drawing helpers ----------------------------------------------------------

func _panel(r: Rect2, edge: Color) -> void:
	draw_rect(r, PANEL)
	draw_rect(r, Color(edge, 0.85), false, 2.0)
	draw_rect(Rect2(r.position + Vector2(2, 2), Vector2(r.size.x - 4, 2)), Color(1, 1, 1, 0.06))


func _text(pos: Vector2, s: String, fs: int, c: Color, outline := 3) -> void:
	draw_string_outline(_font, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, outline, Color(0, 0, 0, c.a * 0.8))
	draw_string(_font, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, c)


func _text_c(pos: Vector2, s: String, fs: int, c: Color, outline := 3) -> void:
	var tw := _font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	_text(Vector2(pos.x - tw * 0.5, pos.y), s, fs, c, outline)


func _text_r(pos: Vector2, s: String, fs: int, c: Color) -> void:
	var tw := _font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	_text(Vector2(pos.x - tw, pos.y), s, fs, c)


static func format_time(t: float) -> String:
	if t <= 0.0:
		return "--:--.--"
	var m := int(t / 60.0)
	var s := fmod(t, 60.0)
	return "%02d:%05.2f" % [m, s]


static func _fmt_points(v: int) -> String:
	var s := str(absi(v))
	var out := ""
	while s.length() > 3:
		out = " " + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	return ("-" if v < 0 else "") + s + out


static func _ordinal(n: int) -> String:
	match n:
		1:
			return "1ST"
		2:
			return "2ND"
		3:
			return "3RD"
	return "%dTH" % n
