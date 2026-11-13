class_name DayCycle
extends Node
## Time of day and weather that change during a race: the light drifts from
## day through golden hour and dusk into night (and back), and rain can roll
## in for a while — wet asphalt has less grip, headlights switch on at dusk.

const PERIOD := 240.0   # seconds for a full day
const KEYS := [
	[0.0, Color(1.0, 1.0, 1.0)], [0.25, Color(1.0, 0.9, 0.78)], [0.45, Color(0.8, 0.66, 0.88)],
	[0.6, Color(0.46, 0.49, 0.72)], [0.8, Color(0.46, 0.49, 0.72)], [0.92, Color(0.85, 0.8, 0.95)], [1.0, Color(1.0, 1.0, 1.0)],
]

var race: Node
var track: Track
var views: LocalMultiplayerManager
var enabled := true
var phase := 0.0
var _modulate: CanvasModulate
var _base := Color.WHITE
var _rain_at := -1.0
var _rain_end := -1.0
var _t := 0.0
var _base_weather := ""
var _was_dark := false


func setup(the_race: Node, the_track: Track, the_views: LocalMultiplayerManager) -> void:
	race = the_race
	track = the_track
	views = the_views
	Game.darkness = 0.0
	Game.raining = false
	# Tracks that are always night, or the digital void, keep their light.
	if track.theme_name in ["neon", "midnight", "vector", "sumo"] or not bool(SaveManager.get_setting("dynamic_weather", true)):
		enabled = false
		Game.darkness = 1.0 if track.night else 0.0
		return
	for c in track.get_children():
		if c is CanvasModulate:
			_modulate = c
	if _modulate == null:
		_modulate = CanvasModulate.new()
		track.add_child(_modulate)
	_base = _modulate.color
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	phase = rng.randf_range(0.0, 0.3)
	_base_weather = Weather.kind_for_theme(track.theme_name)
	if track.theme_name != "desk" and rng.randf() < 0.7:
		_rain_at = rng.randf_range(40.0, 90.0)
		_rain_end = _rain_at + rng.randf_range(40.0, 70.0)


func _process(delta: float) -> void:
	if not enabled:
		return
	_t += delta
	phase = fmod(phase + delta / PERIOD, 1.0)
	var c := _sample(phase)
	if Game.raining:
		c = c.darkened(0.15)
	_modulate.color = _base * c
	Game.darkness = clampf(1.0 - c.get_luminance() * 1.25, 0.0, 1.0) * 1.6
	var dark := Game.darkness > 0.35
	if dark != _was_dark:
		_was_dark = dark
		views.message_all(tr("NIGHT FALLS") if dark else tr("SUNRISE"), UiTheme.CYAN, 1.5)
	if _rain_at > 0.0 and _t >= _rain_at and not Game.raining and _t < _rain_end:
		_set_rain(true)
	elif Game.raining and _t >= _rain_end:
		_set_rain(false)


func _set_rain(on: bool) -> void:
	Game.raining = on
	var kind := "snow" if track.theme_name == "snow" else "rain"
	for w in views.weathers:
		(w as Weather).set_kind(kind if on else _base_weather)
	views.message_all(tr("RAIN — LESS GRIP!") if on else tr("THE RAIN STOPS"), UiTheme.CYAN, 1.6)


static func _sample(f: float) -> Color:
	for k in KEYS.size() - 1:
		var a: Array = KEYS[k]
		var b: Array = KEYS[k + 1]
		if f >= float(a[0]) and f <= float(b[0]):
			var t := (f - float(a[0])) / maxf(float(b[0]) - float(a[0]), 0.0001)
			return (a[1] as Color).lerp(b[1], t)
	return Color.WHITE
