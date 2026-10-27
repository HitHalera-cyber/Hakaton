extends Node
## Sound effects and music, synthesised at startup — the project ships with
## no audio files, so there is nothing to license. Music is a short synthwave
## loop per location, composed and rendered on a worker thread.
## Buses: Master > Music / Engine / SFX (volumes come from the settings).

const MIX_RATE := 22050
const BUSES := ["Music", "Engine", "SFX"]

const STYLES := {
	"menu":   {"bpm": 104, "roots": [53, 55, 52, 57], "minor": [false, false, true, true], "lead": 0.8},
	"sunset": {"bpm": 100, "roots": [57, 53, 48, 55], "minor": [true, false, false, false], "lead": 1.0},
	"night":  {"bpm": 112, "roots": [54, 50, 57, 52], "minor": [true, false, false, false], "lead": 1.0},
	"forest": {"bpm": 96,  "roots": [50, 48, 46, 48], "minor": [true, false, false, false], "lead": 0.7},
	"snow":   {"bpm": 90,  "roots": [52, 48, 55, 50], "minor": [true, false, false, false], "lead": 0.9},
}

var _sfx: Dictionary = {}
var _players: Array = []
var _next_player := 0
var _music: AudioStreamPlayer
var _music_cache: Dictionary = {}
var _thread: Thread
var _thread_style := ""
var _wanted_style := ""
var _current_style := ""
var _mbuf := PackedFloat32Array()   # music render buffer (worker thread only)


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_ensure_buses()
	apply_volumes()
	_build_sfx()
	for i in 10:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_players.append(p)
	_music = AudioStreamPlayer.new()
	_music.bus = "Music"
	add_child(_music)


func _exit_tree() -> void:
	if _thread and _thread.is_started():
		_thread.wait_to_finish()


func _ensure_buses() -> void:
	for b in BUSES:
		if AudioServer.get_bus_index(b) == -1:
			AudioServer.add_bus()
			var idx := AudioServer.bus_count - 1
			AudioServer.set_bus_name(idx, b)
			AudioServer.set_bus_send(idx, "Master")


func apply_volumes() -> void:
	_set_bus("Master", float(SaveManager.get_setting("master_volume", 0.8)))
	_set_bus("Music", float(SaveManager.get_setting("music_volume", 0.6)))
	_set_bus("Engine", float(SaveManager.get_setting("engine_volume", 0.7)))
	_set_bus("SFX", float(SaveManager.get_setting("sfx_volume", 0.8)))


func _set_bus(bus: String, linear: float) -> void:
	var idx := AudioServer.get_bus_index(bus)
	if idx >= 0:
		AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(linear, 0.0001)))
		AudioServer.set_bus_mute(idx, linear <= 0.001)


# --- effects --------------------------------------------------------------

func play(sfx_name: String, pitch := 1.0, volume_db := 0.0) -> void:
	if not _sfx.has(sfx_name):
		return
	var p: AudioStreamPlayer = _players[_next_player]
	_next_player = (_next_player + 1) % _players.size()
	p.stream = _sfx[sfx_name]
	p.pitch_scale = pitch
	p.volume_db = volume_db
	p.play()


func _build_sfx() -> void:
	_sfx["ui_move"] = _wav(_tone([[880.0, 0.035]], "square", 0.25))
	_sfx["ui_select"] = _wav(_tone([[660.0, 0.05], [990.0, 0.07]], "square", 0.3))
	_sfx["ui_back"] = _wav(_tone([[520.0, 0.05], [390.0, 0.07]], "square", 0.25))
	_sfx["ui_error"] = _wav(_tone([[180.0, 0.12]], "saw", 0.3))
	_sfx["count"] = _wav(_tone([[440.0, 0.18]], "square", 0.3))
	_sfx["go"] = _wav(_tone([[880.0, 0.35]], "square", 0.3))
	_sfx["lap"] = _wav(_tone([[784.0, 0.07], [1046.0, 0.12]], "square", 0.3))
	_sfx["reward"] = _wav(_tone([[523.0, 0.07], [659.0, 0.07], [784.0, 0.07], [1046.0, 0.2]], "square", 0.28))
	_sfx["unlock"] = _wav(_tone([[392.0, 0.08], [523.0, 0.08], [659.0, 0.08], [784.0, 0.08], [1046.0, 0.3]], "triangle", 0.4))
	_sfx["drift_bank"] = _wav(_tone([[1046.0, 0.05], [1318.0, 0.08]], "triangle", 0.3))
	_sfx["drift_fail"] = _wav(_tone([[300.0, 0.08], [200.0, 0.14]], "saw", 0.25))
	_sfx["crash"] = _wav(_noise_burst(0.35, 0.6, 0.15))
	_sfx["bump"] = _wav(_noise_burst(0.15, 0.4, 0.35))
	_sfx["handbrake"] = _wav(_noise_burst(0.12, 0.2, 0.05))


func _tone(notes: Array, wave: String, vol: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	for n in notes:
		var freq: float = n[0]
		var count := int(float(n[1]) * MIX_RATE)
		var ph := 0.0
		for i in count:
			var env := 1.0 - float(i) / count
			ph = fmod(ph + freq / MIX_RATE, 1.0)
			out.append(_osc(wave, ph) * vol * env)
	return out


func _noise_burst(length: float, vol: float, brightness: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	var count := int(length * MIX_RATE)
	var lp := 0.0
	var rng := RandomNumberGenerator.new()
	rng.seed = 99
	for i in count:
		var env := pow(1.0 - float(i) / count, 2.5)
		lp += (rng.randf_range(-1.0, 1.0) - lp) * brightness
		var thump := sin(TAU * 70.0 * i / MIX_RATE) * 0.5 * env
		out.append((lp * 1.6 + thump) * vol * env)
	return out


static func _osc(wave: String, ph: float) -> float:
	match wave:
		"square":
			return 1.0 if ph < 0.5 else -1.0
		"pulse":
			return 1.0 if ph < 0.25 else -1.0
		"saw":
			return ph * 2.0 - 1.0
		"triangle":
			return 4.0 * absf(ph - 0.5) - 1.0
	return sin(ph * TAU)


static func _encode(samples: PackedFloat32Array) -> PackedByteArray:
	var bytes := PackedByteArray()
	bytes.resize(samples.size() * 2)
	for i in samples.size():
		bytes.encode_s16(i * 2, int(clampf(samples[i], -1.0, 1.0) * 32000.0))
	return bytes


func _wav(samples: PackedFloat32Array, loop := false) -> AudioStreamWAV:
	return _wav_from_bytes(_encode(samples), samples.size(), loop)


func _wav_from_bytes(bytes: PackedByteArray, frames: int, loop: bool) -> AudioStreamWAV:
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = MIX_RATE
	w.stereo = false
	w.data = bytes
	if loop:
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD
		w.loop_begin = 0
		w.loop_end = frames
	return w


# --- music ------------------------------------------------------------------

func play_music(style: String) -> void:
	if not STYLES.has(style):
		style = "menu"
	_wanted_style = style
	if style == _current_style and _music.playing:
		return
	if _music_cache.has(style):
		_start_music(style)
	elif _thread == null or not _thread.is_started():
		_launch(style)


func stop_music() -> void:
	_wanted_style = ""
	_current_style = ""
	_music.stop()


func _launch(style: String) -> void:
	_thread = Thread.new()
	_thread_style = style
	_thread.start(_render_music.bind(style))


func _process(_delta: float) -> void:
	if _thread and _thread.is_started() and not _thread.is_alive():
		var result: Array = _thread.wait_to_finish()
		_music_cache[_thread_style] = _wav_from_bytes(result[0], result[1], true)
		_thread = null
		if _wanted_style != "":
			if _music_cache.has(_wanted_style):
				_start_music(_wanted_style)
			else:
				_launch(_wanted_style)


func _start_music(style: String) -> void:
	_current_style = style
	_music.stream = _music_cache[style]
	_music.volume_db = -4.0
	_music.play()


## Worker thread: composes and renders an 8-bar loop. Returns [bytes, frames].
func _render_music(style: String) -> Array:
	var st: Dictionary = STYLES[style]
	var bpm: float = st["bpm"]
	var beat := 60.0 / bpm
	var bars := 8
	var total := int(bars * 4 * beat * MIX_RATE)
	_mbuf = PackedFloat32Array()
	_mbuf.resize(total)
	_mbuf.fill(0.0)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(style)
	var roots: Array = st["roots"]
	var minor: Array = st["minor"]
	var lead_amt: float = st["lead"]
	for bar in bars:
		var ci := bar % 4
		var root: int = roots[ci]
		var third := 3 if minor[ci] else 4
		var chord := [root, root + third, root + 7]
		var bar_start := bar * 4 * beat
		# Pad: whole-bar chord on a soft triangle.
		for n in chord:
			_note(bar_start, beat * 4.0, _midi(n), "triangle", 0.05, 0.3, 0.6)
		# Bass: driving eighths on the root.
		for e in 8:
			var bn := root - 24 if e % 4 != 3 else root - 12
			_note(bar_start + e * beat * 0.5, beat * 0.45, _midi(bn), "saw", 0.16, 0.005, 0.25, 0.25)
		# Arpeggio from bar 3 on, a lead line in the second half.
		if bar >= 2:
			var pattern := [0, 1, 2, 1, 0, 2, 1, 2]
			for s in 16:
				var tone: int = chord[pattern[s % 8]] + 12 + (12 if s % 8 >= 6 else 0)
				_note(bar_start + s * beat * 0.25, beat * 0.2, _midi(tone), "pulse", 0.04, 0.002, 0.08)
		if bar >= 4 and lead_amt > 0.0:
			var t := 0.0
			while t < 4.0:
				var dur: float = [0.5, 1.0, 1.5][rng.randi_range(0, 2)]
				var deg: int = [0, 3, 5, 7, 10, 12][rng.randi_range(0, 5)] if minor[ci] else [0, 4, 7, 9, 12][rng.randi_range(0, 4)]
				_note(bar_start + t * beat, beat * dur * 0.9, _midi(root + 12 + deg), "square", 0.05 * lead_amt, 0.01, 0.5)
				t += dur
		# Drums.
		for b in 4:
			_kick(bar_start + b * beat)
			if b % 2 == 1:
				_snare(bar_start + b * beat, rng)
			_hat(bar_start + b * beat + beat * 0.5, rng)
	return [_encode(_mbuf), total]


static func _midi(n: float) -> float:
	return 440.0 * pow(2.0, (n - 69.0) / 12.0)


func _note(start: float, dur: float, freq: float, wave: String, vol: float,
		attack: float, release: float, filter := 1.0) -> void:
	var s0 := int(start * MIX_RATE)
	var count := int((dur + release) * MIX_RATE)
	var ph := 0.0
	var lp := 0.0
	var n := _mbuf.size()
	var att := maxf(attack * MIX_RATE, 1.0)
	var sustain_end := dur * MIX_RATE
	for i in count:
		var env := minf(float(i) / att, 1.0)
		if i > sustain_end:
			env *= maxf(0.0, 1.0 - (i - sustain_end) / (release * MIX_RATE))
		ph = fmod(ph + freq / MIX_RATE, 1.0)
		var v := _osc(wave, ph)
		if filter < 1.0:
			lp += (v - lp) * filter
			v = lp
		var k := (s0 + i) % n
		_mbuf[k] += v * vol * env


func _kick(start: float) -> void:
	var s0 := int(start * MIX_RATE)
	var count := int(0.2 * MIX_RATE)
	var ph := 0.0
	for i in count:
		var t := float(i) / MIX_RATE
		var f := 45.0 + 90.0 * exp(-t * 30.0)
		ph += f / MIX_RATE
		var k := (s0 + i) % _mbuf.size()
		_mbuf[k] += sin(ph * TAU) * 0.35 * exp(-t * 14.0)


func _snare(start: float, rng: RandomNumberGenerator) -> void:
	var s0 := int(start * MIX_RATE)
	var count := int(0.16 * MIX_RATE)
	for i in count:
		var t := float(i) / MIX_RATE
		var k := (s0 + i) % _mbuf.size()
		_mbuf[k] += (rng.randf_range(-1, 1) * 0.18 + sin(TAU * 190.0 * t) * 0.08) * exp(-t * 22.0)


func _hat(start: float, rng: RandomNumberGenerator) -> void:
	var s0 := int(start * MIX_RATE)
	var count := int(0.04 * MIX_RATE)
	var prev := 0.0
	for i in count:
		var t := float(i) / MIX_RATE
		var nz := rng.randf_range(-1, 1)
		var k := (s0 + i) % _mbuf.size()
		_mbuf[k] += (nz - prev) * 0.05 * exp(-t * 90.0)
		prev = nz
