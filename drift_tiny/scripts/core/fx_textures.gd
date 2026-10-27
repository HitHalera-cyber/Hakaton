class_name FxTextures
extends RefCounted
## Small procedurally generated textures shared by particles and lights.

static var _cache: Dictionary = {}


## Soft round puff for smoke, dust and snow spray.
static func puff() -> Texture2D:
	if not _cache.has("puff"):
		var img := Image.create(8, 8, false, Image.FORMAT_RGBA8)
		for y in 8:
			for x in 8:
				var d := Vector2(x - 3.5, y - 3.5).length() / 4.0
				var a := clampf(1.0 - d, 0.0, 1.0)
				# Hard-ish steps keep the pixel-art look.
				a = snappedf(a, 0.34)
				img.set_pixel(x, y, Color(1, 1, 1, a))
		_cache["puff"] = ImageTexture.create_from_image(img)
	return _cache["puff"]


## 1x1 white pixel (sparks, rain).
static func pixel() -> Texture2D:
	if not _cache.has("pixel"):
		var img := Image.create(2, 2, false, Image.FORMAT_RGBA8)
		img.fill(Color.WHITE)
		_cache["pixel"] = ImageTexture.create_from_image(img)
	return _cache["pixel"]


## Radial falloff used by street lamps and neon glow.
static func radial_light() -> Texture2D:
	if not _cache.has("radial"):
		var g := Gradient.new()
		g.set_color(0, Color(1, 1, 1, 1))
		g.set_color(1, Color(1, 1, 1, 0))
		var t := GradientTexture2D.new()
		t.gradient = g
		t.width = 64
		t.height = 64
		t.fill = GradientTexture2D.FILL_RADIAL
		t.fill_from = Vector2(0.5, 0.5)
		t.fill_to = Vector2(1.0, 0.5)
		_cache["radial"] = t
	return _cache["radial"]


## Headlight cone pointing to +X, apex on the left edge.
static func headlight_cone() -> Texture2D:
	if not _cache.has("cone"):
		var w := 64
		var h := 48
		var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
		for y in h:
			for x in w:
				var fx := float(x) / w
				var dy := absf(y - h * 0.5) / (h * 0.5)
				var spread := 0.15 + fx * 0.85
				var a := 0.0
				if dy < spread:
					a = (1.0 - dy / spread) * (1.0 - fx) * 1.4
				img.set_pixel(x, y, Color(1, 1, 1, clampf(a, 0.0, 1.0)))
		_cache["cone"] = ImageTexture.create_from_image(img)
	return _cache["cone"]


## Tileable noise texture for ground (grass, sand, snow, pavement).
static func ground(key: String, base: Color, dark: Color, light: Color, seed_value: int, density := 0.18) -> Texture2D:
	var ck := "ground_" + key
	if not _cache.has(ck):
		var img := Image.create(64, 64, false, Image.FORMAT_RGBA8)
		var rng := RandomNumberGenerator.new()
		rng.seed = seed_value
		img.fill(base)
		for i in int(64 * 64 * density):
			var x := rng.randi_range(0, 63)
			var y := rng.randi_range(0, 63)
			img.set_pixel(x, y, dark if rng.randf() < 0.6 else light)
		# a few 2px clumps
		for i in 40:
			var x := rng.randi_range(0, 62)
			var y := rng.randi_range(0, 62)
			var c := dark.darkened(0.1)
			img.set_pixel(x, y, c)
			img.set_pixel(x + 1, y, c)
			img.set_pixel(x, y + 1, c)
		_cache[ck] = ImageTexture.create_from_image(img)
	return _cache[ck]
