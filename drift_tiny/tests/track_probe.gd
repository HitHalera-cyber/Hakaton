extends Node
## Prints per-track generated content (shortcuts, hazards, drift zones) and
## how long building the track data takes. Run headless.


func _ready() -> void:
	for td in Game.tracks:
		var t0 := Time.get_ticks_msec()
		var d := Game.track_data(td["id"])
		print("%-10s shortcuts=%d hazards=%d zones=%d build=%dms" % [td["id"], d.shortcuts.size(), d.hazards.size(), d.drift_zones.size(), Time.get_ticks_msec() - t0])
	get_tree().quit()
