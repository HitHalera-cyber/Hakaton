class_name DriftScoring
extends RefCounted
## Drift points of one car. A combo ("chain") runs while the car keeps
## drifting; short breaks between corners are allowed (CHAIN_WINDOW). The chain
## is banked as points x multiplier when it ends cleanly, and lost on a crash,
## a spin or leaving the road.

signal popup(text: String, points: int, kind: String)

const CHAIN_WINDOW := 1.4
const MIN_SLIP := 12.0
const MIN_SPEED := 60.0
const MAX_MULT := 5.0
const MULT_RATE := 0.32       # multiplier gained per second of drifting
const BASE_RATE := 140.0      # points per second at 45 degrees and ~200 px/s

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
var tandem := false          # set by the race in co-op when both cars drift close
var proximity := false       # true this frame if hugging the road edge


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


func update(dt: float, car: Car) -> void:
	if not enabled:
		return
	var drifting_well := car.drifting and car.slip_deg > MIN_SLIP and car.speed > MIN_SPEED and car.on_road
	proximity = false
	if drifting_well:
		var angle_f := clampf((car.slip_deg - 8.0) / 37.0, 0.0, 1.4)
		var speed_f := clampf(car.speed / 200.0, 0.3, 1.6)
		var edge_f := 1.0
		if car.edge_dist < 9.0:
			edge_f = 1.5
			proximity = true
		var tandem_f := 1.5 if tandem else 1.0
		current += BASE_RATE * angle_f * speed_f * edge_f * tandem_f * dt
		multiplier = minf(multiplier + MULT_RATE * dt * (1.0 + float(int(chain_time) / 4) * 0.25), MAX_MULT)
		chain_timer = CHAIN_WINDOW
		chain_time += dt
		in_chain = true
	elif in_chain:
		if not car.on_road:
			clean = false
		chain_timer -= dt
		if chain_timer <= 0.0:
			bank()


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
	best_combo = maxi(best_combo, pts)
	drifts_banked += 1
	if pts > 0:
		popup.emit(label + (" CLEAN" if clean and pts > 150 else ""), pts, "bank")
	_clear_chain()


## Chain lost (crash, spin, respawn).
func fail(reason: String) -> void:
	if in_chain and current > 5.0 and reason != "":
		popup.emit(reason, int(current * multiplier), "fail")
	_clear_chain()


## Light contact: the combo survives but loses the clean bonus.
func touch() -> void:
	if in_chain:
		clean = false


func shown_points() -> int:
	return int(current * multiplier)
