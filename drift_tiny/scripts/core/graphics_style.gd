class_name GraphicsStyle
extends RefCounted
## Visual presets for the whole game. A style sets the pixel size of the
## world (render resolution), a post-processing look (shaders/post.gdshader)
## and a few drawing switches used by Track and CarPainter.

const STYLES := {
	"neon_sunset": {
		"name": "Neon Sunset",
		"desc": "Synthwave dusk: purple shadows, pink neon, 480x270.",
		"shrink": 2, "outline": false, "night": false, "toy": false, "sunset_tint": true,
		"post": {"saturation": 1.1, "contrast": 1.05, "vignette": 0.25},
	},
	"toy_racer": {
		"name": "Toy Racer",
		"desc": "Bright toy-box colours, chunky 320x180 pixels, outlined cars, banners and tyre walls.",
		"shrink": 3, "outline": true, "night": false, "toy": true, "sunset_tint": false,
		"post": {"saturation": 1.4, "contrast": 1.12, "brightness": 0.03},
	},
	"night_city": {
		"name": "Night Drive",
		"desc": "Every track at night: cold colours, street lamps and headlight beams.",
		"shrink": 2, "outline": false, "night": true, "toy": false, "sunset_tint": false,
		"post": {"saturation": 0.8, "contrast": 1.08, "tint": Vector3(0.9, 0.95, 1.1)},
	},
	"handheld": {
		"name": "Handheld 4-shade",
		"desc": "Four shades of green with dithering, like an old handheld console. 320x180.",
		"shrink": 3, "outline": true, "night": false, "toy": false, "sunset_tint": false,
		"post": {"palette_mode": 1, "contrast": 1.1},
	},
	"crt_arcade": {
		"name": "CRT Arcade",
		"desc": "Arcade cabinet tube: scanlines, glow at the edges, colour fringing.",
		"shrink": 2, "outline": false, "night": false, "toy": false, "sunset_tint": true,
		"post": {"saturation": 1.25, "contrast": 1.15, "scanlines": 0.35, "vignette": 0.6, "aberration": 0.6, "palette_mode": 2, "posterize_levels": 7.0},
	},
}

const ORDER := ["neon_sunset", "toy_racer", "night_city", "handheld", "crt_arcade"]

static var _shader: Shader


static func current_id() -> String:
	var id := str(SaveManager.get_setting("style", "neon_sunset"))
	return id if STYLES.has(id) else "neon_sunset"


static func current() -> Dictionary:
	return STYLES[current_id()]


static func flag(key: String) -> bool:
	return bool(current().get(key, false))


## Applies the current style to a view container (pixel size + post shader).
static func apply_to_view(svc: SubViewportContainer) -> void:
	var st := current()
	svc.stretch_shrink = int(st["shrink"])
	if _shader == null:
		_shader = load("res://shaders/post.gdshader")
	var mat := ShaderMaterial.new()
	mat.shader = _shader
	var post: Dictionary = st["post"]
	for key in post.keys():
		mat.set_shader_parameter(key, post[key])
	svc.material = mat
	# Keep source_size right when the container is resized.
	var update := func():
		mat.set_shader_parameter("source_size", svc.size / float(svc.stretch_shrink))
	svc.resized.connect(update)
	update.call()
