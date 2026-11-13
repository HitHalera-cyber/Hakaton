extends Node
## Game-wide data (cars, tracks, modes) and the settings of the race that is
## about to start. Scenes read the session from here.

const SCENES := {
	"menu": "res://scenes/main_menu.tscn",
	"setup": "res://scenes/race_setup.tscn",
	"garage": "res://scenes/garage.tscn",
	"race": "res://scenes/race.tscn",
	"records": "res://scenes/records.tscn",
	"settings": "res://scenes/settings.tscn",
}

const MODES := {
	"time_attack": {"name": "Time Attack", "players": [1, 2], "desc": "Beat the clock. Fastest total time wins."},
	"drift_attack": {"name": "Drift Attack", "players": [1, 2], "desc": "Score as many drift points as you can before the last lap ends."},
	"practice": {"name": "Practice", "players": [1, 2], "desc": "Free driving. No finish line, lap times are still shown."},
	"championship": {"name": "Championship", "players": [1, 2], "desc": "All four tracks against CPU rivals. Points for places and style."},
	"ghost": {"name": "Ghost Race", "players": [1], "desc": "Race against the replay of your best lap."},
	"versus": {"name": "Local Versus", "players": [2], "desc": "Head to head: first over the line wins, drift points break ties."},
	"coop": {"name": "Local Co-op", "players": [2], "desc": "Team drift score. Drift side by side for the tandem bonus."},
	"gymkhana": {"name": "Gymkhana", "players": [1, 2], "desc": "90 seconds on an open lot: donuts around the posts, figure eights, ramps and boost pads."},
	"tandem": {"name": "Tandem Chase", "players": [2], "desc": "One leads, one chases: the chaser scores for drifting close behind. Roles swap every lap."},
	"training": {"name": "Training", "players": [1], "desc": "Step-by-step lessons: throttle, steering, handbrake drift, boost and donuts."},
	"police": {"name": "Police Chase", "players": [1, 2], "desc": "Downtown: robbers grab cash and stay free for 2:30, cops box them in. Pick your side; bots take the rest."},
	"bomb": {"name": "Hot Potato", "players": [1, 2], "desc": "Downtown: the bomb passes on contact. Get rid of it before the fuse runs out. Last car left wins."},
	"elimination": {"name": "Elimination", "players": [1, 2], "desc": "Every 20 seconds the last car is knocked out. Be the last one standing."},
	"delivery": {"name": "Courier Rush", "players": [1, 2], "desc": "Downtown: pick up parcels and deliver them before their timers run out. Quick drops pay more. 3:00."},
	"koth": {"name": "King of the Hill", "players": [1, 2], "desc": "Downtown: hold the glowing zone. Alone inside you score fast, crowded it barely counts - push them out. It moves every 25 s."},
	"soccer": {"name": "Car Soccer", "players": [1, 2], "desc": "Stadium: blue against red, push the ball into the other goal. Bots fill both teams. First to 5 or 3:00."},
	"sumo": {"name": "Sumo", "players": [1, 2], "desc": "A round platform above the void, no walls. Push the others off, stay on yourself. 3 rounds."},
	"gates": {"name": "Gate Rush", "players": [1, 2], "desc": "Stadium slalom: drive through the cone gates in order. Every gate adds time, a gate taken in a drift adds more."},
}

## Championship points for places 1..4.
const PLACE_POINTS := [10, 7, 5, 3]

var cars: Array = []          # Array of Dictionaries from data/cars.json
var car_config: Dictionary = {}
var tracks: Array = []        # Array of Dictionaries from data/tracks.json

# Session of the race being set up / played.
var players := 1
var mode := "time_attack"
var track_id := "mountain"
var laps := 3
var view_mode := "split"
var reverse := false        # drive the track the other way
var bots := 3               # CPU cars in race modes / hot potato
var bot_skill := 1          # 0 easy, 1 normal, 2 hard
var roles: Array = ["robber", "cop"]   # police chase: side of 1P and 2P
var cops := 3               # police chase: cops in total (players + bots)
# Set by the race's day cycle: 0 = bright day, 1 = deep night; rain lowers grip.
var darkness := 0.0
var raining := false

## Championship state: {"tracks": [...], "index": int, "points": {name: int}}
var championship: Dictionary = {}

var _track_cache: Dictionary = {}
var _fps_label: Label


func _ready() -> void:
	car_config = _load_json("res://data/cars.json")
	cars = car_config.get("cars", [])
	tracks = _load_json("res://data/tracks.json").get("tracks", [])
	view_mode = str(SaveManager.get_setting("two_player_view", "split"))
	_apply_display_settings()
	_build_fps_overlay()


func _load_json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("Missing data file: " + path)
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("Bad JSON in " + path)
		return {}
	return parsed


func goto(scene_key: String) -> void:
	get_tree().paused = false
	darkness = 0.0
	raining = false
	get_tree().change_scene_to_file(SCENES[scene_key])


# --- lookups ----------------------------------------------------------------

func car_def(id: String) -> Dictionary:
	for c in cars:
		if c["id"] == id:
			return c
	return cars[0]


func car_ids() -> Array:
	var out: Array = []
	for c in cars:
		out.append(c["id"])
	return out


func track_def(id: String) -> Dictionary:
	for t in tracks:
		if t["id"] == id:
			return t
	return tracks[0]


func track_ids() -> Array:
	var out: Array = []
	for t in tracks:
		out.append(t["id"])
	return out


## Built TrackData (spline samples etc.), cached because building takes a moment.
func track_data(id: String, reversed := false) -> TrackData:
	if id == "arena":
		if not _track_cache.has("arena"):
			var a := TrackData.new()
			a.setup_arena()
			_track_cache["arena"] = a
		return _track_cache["arena"]
	if id in ["stadium", "sumo"]:
		if not _track_cache.has(id):
			var fdata := TrackData.new()
			fdata.setup_field(id)
			_track_cache[id] = fdata
		return _track_cache[id]
	if id == "city":
		if not _track_cache.has("city"):
			var cdata := TrackData.new()
			cdata.setup_city()
			_track_cache["city"] = cdata
		return _track_cache["city"]
	var key := id + ("_rev" if reversed else "")
	if not _track_cache.has(key):
		var td := TrackData.new()
		td.setup(track_def(id), reversed)
		_track_cache[key] = td
	return _track_cache[key]


func modes_for(player_count: int) -> Array:
	var out: Array = []
	for key in MODES.keys():
		if player_count in MODES[key]["players"]:
			out.append(key)
	return out


func mode_name(key: String) -> String:
	return MODES.get(key, {}).get("name", key)


func color_from_index(i: int) -> Color:
	var cols: Array = car_config.get("colors", ["ffffff"])
	return Color.html(cols[posmod(i, cols.size())])


## Colour of a car as the player painted it (or the factory colour).
func car_color(car_id: String) -> Color:
	var st := SaveManager.car_state(car_id)
	var idx := int(st["color"])
	if idx < 0:
		idx = int(car_def(car_id).get("color", 0))
	return color_from_index(idx)


# --- championship -------------------------------------------------------------

## Tracks of the cup (groups of 4 in tracks.json order) that holds a track.
func cup_tracks(any_track: String) -> Array:
	var ids := track_ids()
	var g := maxi(ids.find(any_track), 0) / 4
	return ids.slice(g * 4, mini(g * 4 + 4, ids.size()))


func start_championship(any_track := "") -> void:
	championship = {"tracks": cup_tracks(any_track), "index": 0, "points": {}}
	reverse = false
	track_id = championship["tracks"][0]
	mode = "championship"


func championship_active() -> bool:
	return mode == "championship" and not championship.is_empty()


## Returns false when the championship is over.
func advance_championship() -> bool:
	championship["index"] = int(championship["index"]) + 1
	if int(championship["index"]) >= championship["tracks"].size():
		return false
	track_id = championship["tracks"][championship["index"]]
	return true


# --- display --------------------------------------------------------------

func _apply_display_settings() -> void:
	set_fullscreen(bool(SaveManager.get_setting("fullscreen", false)))
	set_vsync(bool(SaveManager.get_setting("vsync", true)))
	set_integer_scaling(bool(SaveManager.get_setting("integer_scaling", false)))


## Graphics quality: 0 low, 1 medium, 2 high.
func quality() -> int:
	return clampi(int(SaveManager.get_setting("quality", 2)), 0, 2)


## Picks the value for the current quality from [low, medium, high].
func by_quality(values: Array) -> Variant:
	return values[quality()]


func _build_fps_overlay() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 100
	add_child(layer)
	_fps_label = Label.new()
	_fps_label.position = Vector2(4, 0)
	_fps_label.add_theme_font_size_override("font_size", 14)
	_fps_label.add_theme_color_override("font_color", Color("ffe14d"))
	_fps_label.add_theme_color_override("font_outline_color", Color.BLACK)
	_fps_label.add_theme_constant_override("outline_size", 4)
	layer.add_child(_fps_label)
	set_show_fps(bool(SaveManager.get_setting("show_fps", false)))


func set_show_fps(on: bool) -> void:
	_fps_label.visible = on
	set_process(on)


func _process(_delta: float) -> void:
	_fps_label.text = "FPS %d" % Engine.get_frames_per_second()


func set_fullscreen(on: bool) -> void:
	if on:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)


func set_vsync(on: bool) -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if on else DisplayServer.VSYNC_DISABLED)


func set_integer_scaling(on: bool) -> void:
	var root := get_tree().root
	if "content_scale_stretch" in root:
		root.set("content_scale_stretch", 1 if on else 0)
