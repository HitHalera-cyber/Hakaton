class_name DriftScoring
extends RefCounted
## Drift points of one car. A combo ("chain") runs while the car keeps
## drifting; short breaks between corners are allowed (CHAIN_WINDOW). The chain
## is banked as points x multiplier when it ends cleanly, and lost on a crash,
## a spin or leaving the road.
##
## Drift zones (the sharpest corners, marked on the road) double the points
## earned inside them and give a grade S/A/B/C on exit for how much of the
## zone was driven sideways. The zone bonus is paid at once and cannot be lost.

signal popup(text: String, points: int, kind: String)

const CHAIN_WINDOW := 2.0
const MIN_SLIP := 12.0
const MIN_SPEED := 60.0
const MAX_MULT := 5.0
const MULT_RATE := 0.5        # multiplier gained per second of drifting
const BASE_RATE := 220.0      # points per second at 45 degrees and ~200 px/s
const ZONE_FACTOR := 2.0
const ZONE_GRADES := [["S", 0.9, 1500], ["A", 0.75, 1000], ["B", 0.5, 600], ["C", 0.25, 300]]

var enabled := false
var total := 0
var current := 0.0
var multiplier := 1.0
var in_chain := false
var chain_timer := 0.0
var chain_time := 0.0
var clean := true
var best_combo := 0
var drifts_banked := 0
var zones_s := 0
var clock := 0.0              # race time, set by the race every tick
var best_window := Vector2.ZERO   # race time span of the best combo (for the replay)
var _chain_start := 0.0
var _last_drift := 0.0
var tandem := false          # set by the race in co-op when both cars drift close
var proximity := false       # true this frame if hugging the road edge

# Current drift zone (-1 outside) and how it is going.
var zone_id := -1
var zone_frames := 0
var zone_drift_frames := 0


func reset() -> void:
	total = 0
	_clear_chain()
	best_combo = 0
	drifts_banked = 0


func _clear_chain() -> void:
	current = 0.0
	multiplier = 1.0
	in_chain = false
	chain_timer = 0.0
	chain_time = 0.0
	clean = true


## Share of the current zone driven sideways so far (0..1).
func zone_ratio() -> float:
	return float(zone_drift_frames) / maxf(float(zone_frames), 1.0)


static func grade_for(ratio: float) -> String:
	for g in ZONE_GRADES:
		if ratio >= float(g[1]):
			return g[0]
	return "-"


func update(dt: float, car: Car) -> void:
	if not enabled:
		return
	var drifting_well := car.drifting and car.slip_deg > MIN_SLIP and car.speed > MIN_SPEED and car.on_road
	_update_zone(car, drifting_well)
	proximity = false
	if drifting_well:
		var angle_f := clampf((car.slip_deg - 8.0) / 37.0, 0.0, 1.4)
		var speed_f := clampf(car.speed / 200.0, 0.3, 1.6)
		var edge_f := 1.0
		if car.edge_dist < 9.0:
			edge_f = 1.5
			proximity = true
		var tandem_f := 1.5 if tandem else 1.0
		var zone_f := ZONE_FACTOR if zone_id >= 0 else 1.0
		current += BASE_RATE * angle_f * speed_f * edge_f * tandem_f * zone_f * dt
		multiplier = minf(multiplier + MULT_RATE * dt * (1.0 + float(int(chain_time) / 3) * 0.25), MAX_MULT)
		chain_timer = CHAIN_WINDOW
		chain_time += dt
		if not in_chain:
			_chain_start = clock
		_last_drift = clock
		in_chain = true
	elif in_chain:
		if not car.on_road:
			clean = false
		chain_timer -= dt
		if chain_timer <= 0.0:
			bank()


func _update_zone(car: Car, drifting_well: bool) -> void:
	var z := car.track.zone_at(car.track_idx) if car.track else -1
	if z != zone_id:
		if zone_id >= 0:
			_finish_zone()
		zone_id = z
		zone_frames = 0
		zone_drift_frames = 0
	if zone_id >= 0:
		zone_frames += 1
		if drifting_well:
			zone_drift_frames += 1


func _finish_zone() -> void:
	var ratio := zone_ratio()
	for g in ZONE_GRADES:
		if ratio >= float(g[1]):
			var bonus := int(g[2])
			total += bonus
			if g[0] == "S":
				zones_s += 1
			popup.emit(Lang.t("ZONE %s") % g[0], bonus, "zone")
			return


func bank() -> void:
	if not in_chain:
		return
	var pts := int(current * multiplier)
	var label := "DRIFT"
	if clean and pts > 150:
		pts = int(pts * 1.15)
	if pts >= 3500:
		label = "PERFECT DRIFT"
	elif pts >= 1200:
		label = "GREAT DRIFT"
	total += pts
	if pts > best_combo:
		best_window = Vector2(_chain_start, _last_drift + 0.4)
	best_combo = maxi(best_combo, pts)
	drifts_banked += 1
	if pts > 0:
		popup.emit(Lang.t(label) + (Lang.t(" CLEAN") if clean and pts > 150 else ""), pts, "bank")
	_clear_chain()


## Chain lost (crash, spin, respawn).
func fail(reason: String) -> void:
	if in_chain and current > 5.0 and reason != "":
		popup.emit(Lang.t(reason), int(current * multiplier), "fail")
	_clear_chain()


## Light contact: the combo survives but loses the clean bonus.
func touch() -> void:
	if in_chain:
		clean = false


func shown_points() -> int:
	return int(current * multiplier)
