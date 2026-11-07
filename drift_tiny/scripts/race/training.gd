class_name TrainingDirector
extends RefCounted
## Training ground: lessons one after another, each with a hint on screen
## and a check on what the car actually does.

const STEPS := [
	["Hold THROTTLE (W / Up / RT) and reach 100 km/h", "speed"],
	["Steer (A-D / Left-Right / stick) and drive one full circle", "circle"],
	["BRAKE (S / Down / LT) and stop the car", "brake"],
	["Hold the HANDBRAKE (Shift / Space / X) while turning to start a drift", "drift"],
	["Keep the slide for 2 seconds: steer into the drift, stay on the throttle", "hold"],
	["Charge the BOOST to orange (2 cells) in a drift, then straighten up", "boost"],
	["Drift a full DONUT around one of the orange posts", "donut"],
]

var car: Car
var gym: Gymkhana
var step := 0
var done := false
var _acc := 0.0
var _top := 0
var _boosted := false
var _donuts0 := 0


func _init(the_car: Car, the_gym: Gymkhana) -> void:
	car = the_car
	gym = the_gym
	car.boosted.connect(func(level: int): _boosted = _boosted or level >= 2)


func hint() -> String:
	if done:
		return Lang.t("Training complete! Press Esc to leave or keep practising.")
	return "%s %d/%d: %s" % [Lang.t("STEP"), step + 1, STEPS.size(), Lang.t(STEPS[step][0])]


## Returns true when a lesson was just completed.
func update(dt: float) -> bool:
	if done:
		return false
	var ok := false
	match STEPS[step][1]:
		"speed":
			ok = car.kmh() >= 100
		"circle":
			_acc += absf(car.angular) * dt
			ok = _acc >= TAU
		"brake":
			_top = maxi(_top, car.kmh())
			ok = _top >= 60 and car.kmh() < 8
		"drift":
			ok = car.drifting and car.slip_deg > 20.0
		"hold":
			ok = car.scoring.chain_time >= 2.0
		"boost":
			ok = _boosted
		"donut":
			ok = gym.donuts > _donuts0
	if not ok:
		return false
	step += 1
	_acc = 0.0
	_top = 0
	_boosted = false
	_donuts0 = gym.donuts
	if step >= STEPS.size():
		done = true
	return true
