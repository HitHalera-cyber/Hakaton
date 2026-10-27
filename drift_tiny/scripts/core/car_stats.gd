class_name CarStats
extends RefCounted
## Effective handling numbers of one car: base values from data/cars.json
## plus the upgrades bought in the garage.

var id := ""
var name := ""
var shape := "hatch"
var length := 15.0
var width := 8.0
var mass := 1.0
var max_speed := 250.0
var accel := 240.0
var brake := 420.0
var grip := 9.5
var drift_grip := 2.2
var steer := 3.0
var drift_steer := 1.3
var power_slide := 0.4
var drift_keep := 0.6
var drift_stability := 1.0
var loose_surface_bonus := 0.0

var color := Color.WHITE
var rims := 0
var decal := 0


static func build(car_id: String, with_upgrades := true) -> CarStats:
	var s := CarStats.new()
	var def: Dictionary = Game.car_def(car_id)
	s.id = def["id"]
	s.name = def.get("name", s.id)
	s.shape = def.get("shape", "hatch")
	for key in ["length", "width", "mass", "max_speed", "accel", "brake", "grip", "drift_grip",
			"steer", "drift_steer", "power_slide", "drift_keep", "drift_stability", "loose_surface_bonus"]:
		if def.has(key):
			s.set(key, float(def[key]))
	var st := SaveManager.car_state(car_id)
	s.color = Game.car_color(car_id)
	s.rims = int(st["rims"])
	s.decal = int(st["decal"])
	if with_upgrades:
		s.apply_upgrades(st["upgrades"], float(def.get("upgrade_bonus", 1.0)))
	return s


func apply_upgrades(levels: Dictionary, bonus: float) -> void:
	var per: Dictionary = Game.car_config.get("upgrades", {}).get("per_level", {})
	for part in per.keys():
		var lvl := float(levels.get(part, 0))
		if lvl <= 0.0:
			continue
		var fx: Dictionary = per[part]
		for stat in fx.keys():
			var cur: float = get(stat)
			set(stat, cur * (1.0 + float(fx[stat]) * lvl * bonus))


## 0..1 bars for the garage screen.
func bars() -> Dictionary:
	return {
		"Speed": clampf((max_speed - 180.0) / 180.0, 0.05, 1.0),
		"Accel": clampf((accel - 180.0) / 200.0, 0.05, 1.0),
		"Grip": clampf((grip - 6.0) / 8.0, 0.05, 1.0),
		"Drift": clampf((power_slide * 0.5 + (3.2 - drift_grip) / 2.4 * 0.5) * drift_steer / 1.3, 0.05, 1.0),
	}


static func upgrade_cost(level: int) -> int:
	var costs: Array = Game.car_config.get("upgrades", {}).get("costs", [250, 600, 1200])
	if level >= costs.size():
		return -1
	return int(costs[level])


static func max_upgrade_level() -> int:
	return int(Game.car_config.get("upgrades", {}).get("max_level", 3))
