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

## Championship state: {"tracks": [...], "index": int, "points": {name: int}}
var championship: Dictionary = {}

var _track_cache: Dictionary = {}


func _ready() -> void:
	car_config = _load_json("res://data/cars.json")
	cars = car_config.get("cars", [])
	tracks = _load_json("res://data/tracks.json").get("tracks", [])
	view_mode = str(SaveManager.get_setting("two_player_view", "split"))
	_apply_display_settings()


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
func track_data(id: String) -> TrackData:
	if not _track_cache.has(id):
		var td := TrackData.new()
		td.setup(track_def(id))
		_track_cache[id] = td
	return _track_cache[id]


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

func start_championship() -> void:
	championship = {"tracks": track_ids(), "index": 0, "points": {}}
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
