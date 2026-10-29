class_name EngineAudio
extends Node
## Real-time engine + tyre squeal synth for the human players' cars, streamed
## through AudioStreamGenerator. Player 1 is panned a little left and player 2
## a little right in two-player races.

const MIX := 22050.0

var _voices: Array = []


class Voice:
	var car: Car
	var player: AudioStreamPlayer
	var playback: AudioStreamGeneratorPlayback
	var pan := 0.0
	var ph := 0.0
	var ph2 := 0.0
	var sq_ph := 0.0
	var lp := 0.0
	var rng := RandomNumberGenerator.new()
	var vol := 0.0
	var squeal := 0.0


func add_car(car: Car, pan: float) -> void:
	var v := Voice.new()
	v.car = car
	v.pan = pan
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = MIX
	gen.buffer_length = 0.12
	v.player = AudioStreamPlayer.new()
	v.player.stream = gen
	v.player.bus = "Engine"
	v.player.volume_db = -6.0
	add_child(v.player)
	v.player.play()
	v.playback = v.player.get_stream_playback() as AudioStreamGeneratorPlayback
	_voices.append(v)


func set_muted(muted: bool) -> void:
	for v in _voices:
		(v as Voice).player.stream_paused = muted


func _process(_delta: float) -> void:
	for v in _voices:
		_fill(v as Voice)


func _fill(v: Voice) -> void:
	if v.playback == null or not is_instance_valid(v.car):
		return
	var frames := v.playback.get_frames_available()
	if frames <= 0:
		return
	var car := v.car
	var rpm := car.rpm
	var freq := 38.0 + rpm * 140.0
	var engine_load := 0.35 + car.input_throttle * 0.65
	var target_vol := 0.25 + 0.35 * engine_load
	var target_sq := 0.0
	if car.drifting or (car.input_handbrake and car.speed > 50.0):
		target_sq = clampf(car.slip_deg / 45.0, 0.2, 1.0) * clampf(car.speed / 150.0, 0.2, 1.0)
	if car.surface_name in ["dirt", "grass", "sand", "snow", "snowbank"]:
		target_sq *= 0.35   # loose surfaces hiss rather than squeal
	var left := 1.0 - maxf(v.pan, 0.0)
	var right := 1.0 + minf(v.pan, 0.0)
	var cutoff := 0.08 + rpm * 0.25
	for i in frames:
		v.vol += (target_vol - v.vol) * 0.002
		v.squeal += (target_sq - v.squeal) * 0.003
		v.ph = fmod(v.ph + freq / MIX, 1.0)
		v.ph2 = fmod(v.ph2 + freq * 0.5 / MIX, 1.0)
		var saw := v.ph * 2.0 - 1.0
		var sub := 1.0 if v.ph2 < 0.5 else -1.0
		var raw := saw * 0.6 + sub * 0.35 + v.rng.randf_range(-1.0, 1.0) * 0.12 * engine_load
		v.lp += (raw - v.lp) * cutoff
		var s := v.lp * v.vol * 0.5
		if v.squeal > 0.01:
			v.sq_ph = fmod(v.sq_ph + (900.0 + v.rng.randf_range(-60.0, 60.0)) / MIX, 1.0)
			s += (sin(v.sq_ph * TAU) * 0.6 + v.rng.randf_range(-1.0, 1.0) * 0.4) * v.squeal * 0.18
		v.playback.push_frame(Vector2(s * left, s * right))
