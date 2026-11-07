extends Node
## Local progress: currency, unlocked cars, per-car tuning, records, settings,
## key bindings and achievements. Everything lives in one JSON file in user://.

signal currency_changed(value: int)
signal achievement_unlocked(id: String, title: String)

const SAVE_PATH := "user://drift_tiny_save.json"
const SAVE_VERSION := 1

const ACHIEVEMENTS := {
	"first_drift": "First Slide — bank your first drift",
	"combo_3k": "Combo Artist — 3 000 points in one combo",
	"combo_10k": "Smoke Machine — 10 000 points in one combo",
	"all_tracks": "Tourist — finish a race on every track",
	"duo": "Couch Crew — finish a two-player race",
	"champion": "Champion — win a championship",
	"collector": "Collector — unlock every car",
	"ghost_buster": "Ghost Buster — beat your own ghost",
}

var data: Dictionary = {}


func _ready() -> void:
	load_game()


func default_data() -> Dictionary:
	return {
		"version": SAVE_VERSION,
		"currency": 600,
		"unlocked": ["classic", "jdm"],
		"selected": ["classic", "jdm"],
		"cars": {},
		"records": {},
		"finished_tracks": [],
		"achievements": [],
		"stars": {},
		# Couch duels: 1P against 2P across all two-player races.
		"duel": {"wins": [0, 0], "draws": 0, "cups": [0, 0], "tracks": {}, "history": []},
		"stats": {"races": 0, "drift_points": 0, "best_combo": 0, "distance": 0.0},
		"bindings": {},
		"settings": {
			"fullscreen": false,
			"vsync": true,
			"integer_scaling": false,
			"master_volume": 0.8,
			"music_volume": 0.6,
			"engine_volume": 0.7,
			"sfx_volume": 0.8,
			"two_player_view": "split",
			"camera_shake": true,
			"pad_layout": 0,
			"show_ghost": true,
			"language": "",
			"quality": 2,
			"style": "neon_sunset",
			"show_fps": false,
			"dynamic_weather": true,
			"replays": true,
		},
	}


func load_game() -> void:
	data = default_data()
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("Save file is damaged, starting fresh.")
		return
	_merge(data, parsed)


## Copies values from src into dst, keeping defaults for missing keys.
func _merge(dst: Dictionary, src: Dictionary) -> void:
	for key in src.keys():
		if dst.has(key) and typeof(dst[key]) == TYPE_DICTIONARY and typeof(src[key]) == TYPE_DICTIONARY:
			_merge(dst[key], src[key])
		else:
			dst[key] = src[key]


func save_game() -> void:
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		push_error("Cannot write save file: %s" % SAVE_PATH)
		return
	f.store_string(JSON.stringify(data, "\t"))


# --- settings -------------------------------------------------------------

func get_setting(key: String, fallback: Variant = null) -> Variant:
	return data["settings"].get(key, fallback)


func set_setting(key: String, value: Variant) -> void:
	data["settings"][key] = value
	save_game()


# --- currency & cars ------------------------------------------------------

func get_currency() -> int:
	return int(data["currency"])


func add_currency(amount: int) -> void:
	data["currency"] = get_currency() + amount
	currency_changed.emit(get_currency())
	save_game()


func spend(amount: int) -> bool:
	if amount > get_currency():
		return false
	data["currency"] = get_currency() - amount
	currency_changed.emit(get_currency())
	save_game()
	return true


func is_unlocked(car_id: String) -> bool:
	return car_id in data["unlocked"]


func unlock_car(car_id: String) -> void:
	if not is_unlocked(car_id):
		data["unlocked"].append(car_id)
		save_game()


## Per-car customisation: colour, rims, decal and upgrade levels.
func car_state(car_id: String) -> Dictionary:
	var cars: Dictionary = data["cars"]
	if not cars.has(car_id):
		cars[car_id] = {
			"color": -1, "rims": 0, "decal": 0,
			"upgrades": {"engine": 0, "tires": 0, "suspension": 0, "brakes": 0},
		}
	var st: Dictionary = cars[car_id]
	for k in ["engine", "tires", "suspension", "brakes"]:
		if not st["upgrades"].has(k):
			st["upgrades"][k] = 0
	return st


func get_selected(player: int) -> String:
	var sel: Array = data["selected"]
	var id: String = sel[clampi(player - 1, 0, sel.size() - 1)]
	return id if is_unlocked(id) else "classic"


func set_selected(player: int, car_id: String) -> void:
	data["selected"][player - 1] = car_id
	save_game()


# --- records --------------------------------------------------------------

func record_key(track_id: String, mode: String) -> String:
	return "%s|%s" % [track_id, mode]


func get_record(track_id: String, mode: String) -> Dictionary:
	return data["records"].get(record_key(track_id, mode), {})


## Stores a result if it beats the old one. Returns the list of fields improved.
func submit_record(track_id: String, mode: String, result: Dictionary) -> Array:
	var key := record_key(track_id, mode)
	var rec: Dictionary = data["records"].get(key, {})
	var improved: Array = []
	var t := float(result.get("time", 0.0))
	if t > 0.0 and (not rec.has("best_time") or t < float(rec["best_time"])):
		rec["best_time"] = t
		rec["car"] = result.get("car", "")
		improved.append("time")
	var lap := float(result.get("best_lap", 0.0))
	if lap > 0.0 and (not rec.has("best_lap") or lap < float(rec["best_lap"])):
		rec["best_lap"] = lap
		improved.append("lap")
	var score := int(result.get("score", 0))
	if score > 0 and score > int(rec.get("best_score", 0)):
		rec["best_score"] = score
		improved.append("score")
	var combo := int(result.get("best_combo", 0))
	if combo > int(rec.get("best_combo", 0)):
		rec["best_combo"] = combo
	data["records"][key] = rec
	save_game()
	return improved


## Challenge stars per track id (reverse tracks have their own): 3 bools.
func get_stars(track_id: String) -> Array:
	var all: Dictionary = data["stars"]
	if not all.has(track_id):
		return [false, false, false]
	return all[track_id]


## Marks star k; returns true if it is new.
func award_star(track_id: String, k: int) -> bool:
	var st := get_stars(track_id).duplicate()
	if st[k]:
		return false
	st[k] = true
	data["stars"][track_id] = st
	save_game()
	return true


## Adds a 1P-vs-2P result. winner: 0 = 1P, 1 = 2P, -1 = draw.
func record_duel(track_id: String, mode: String, winner: int, line: String) -> void:
	var d: Dictionary = data["duel"]
	if winner < 0:
		d["draws"] = int(d["draws"]) + 1
	else:
		var w: Array = d["wins"]
		w[winner] = int(w[winner]) + 1
		var per: Dictionary = d["tracks"]
		var t: Array = per.get(track_id, [0, 0])
		t[winner] = int(t[winner]) + 1
		per[track_id] = t
	var hist: Array = d["history"]
	hist.push_front({"track": track_id, "mode": mode, "winner": winner, "line": line})
	while hist.size() > 8:
		hist.pop_back()
	save_game()


func record_cup_duel(winner: int) -> void:
	if winner >= 0:
		var c: Array = data["duel"]["cups"]
		c[winner] = int(c[winner]) + 1
		save_game()


func duel_wins() -> Array:
	var w: Array = data["duel"]["wins"]
	return [int(w[0]), int(w[1])]


func star_count() -> int:
	var n := 0
	for v in data["stars"].values():
		for b in v:
			if b:
				n += 1
	return n


func mark_track_finished(track_id: String, track_count: int) -> void:
	var done: Array = data["finished_tracks"]
	if not (track_id in done):
		done.append(track_id)
	if done.size() >= track_count:
		unlock_achievement("all_tracks")


func add_stats(drift_points: int, best_combo: int, distance: float) -> void:
	var s: Dictionary = data["stats"]
	s["races"] = int(s["races"]) + 1
	s["drift_points"] = int(s["drift_points"]) + drift_points
	s["best_combo"] = maxi(int(s["best_combo"]), best_combo)
	s["distance"] = float(s["distance"]) + distance
	save_game()


func unlock_achievement(id: String) -> void:
	if not ACHIEVEMENTS.has(id) or (id in data["achievements"]):
		return
	data["achievements"].append(id)
	save_game()
	achievement_unlocked.emit(id, ACHIEVEMENTS[id])


# --- ghosts (kept in separate files, they are big) -------------------------

func ghost_path(track_id: String) -> String:
	return "user://ghost_%s.json" % track_id


func load_ghost(track_id: String) -> Dictionary:
	var path := ghost_path(track_id)
	if not FileAccess.file_exists(path):
		return {}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


func save_ghost(track_id: String, ghost: Dictionary) -> void:
	var f := FileAccess.open(ghost_path(track_id), FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(ghost))


func reset_progress() -> void:
	var keep_settings: Dictionary = data["settings"].duplicate(true)
	var keep_bindings: Dictionary = data["bindings"].duplicate(true)
	data = default_data()
	data["settings"] = keep_settings
	data["bindings"] = keep_bindings
	save_game()
