class_name CarPainter
extends RefCounted
## Draws the pixel-art cars with plain draw calls, so every colour, rim and
## decal combination works without sprite sheets. Local space: car centre at
## the origin, +X is the front. Used by the race car, the ghost, the garage
## preview and the menu.

const TIRE := Color("16161c")
const GLASS := Color("2b3f6b")
const GLASS_HI := Color("6fa8dc")
const HEAD := Color("fff3b0")
const TAIL := Color("8a1c2a")
const TAIL_ON := Color("ff3046")
const RIM_COLORS := [Color("8d8f99"), Color("d9dbe4"), Color("ffffff"), Color("f2c14e")]


static func draw_shadow(ci: CanvasItem, base: Transform2D, length: float, width: float) -> void:
	ci.draw_set_transform_matrix(base)
	var r := Rect2(-length * 0.5, -width * 0.5 - 0.5, length, width + 1.0)
	ci.draw_rect(r, Color(0, 0, 0, 0.35))
	ci.draw_set_transform_matrix(Transform2D.IDENTITY)


static func draw_car(ci: CanvasItem, base: Transform2D, shape: String, length: float, width: float,
		color: Color, rims: int, decal: int, steer_angle := 0.0, braking := false, alpha := 1.0) -> void:
	var L := roundf(length)
	var W := roundf(width)
	var hl := L * 0.5
	var hw := W * 0.5
	var body := color
	var dark := color.darkened(0.35)
	var light := color.lightened(0.3)
	if alpha < 1.0:
		body.a = alpha
		dark.a = alpha
		light.a = alpha
	var tire := Color(TIRE, alpha)
	var rim: Color = RIM_COLORS[clampi(rims, 0, RIM_COLORS.size() - 1)]
	rim.a = alpha

	# Wheels first so the body overlaps them.
	var wheel_out := 1.0 if shape == "wide" else 0.5
	var front_x := hl - 4.0
	var rear_x := -hl + 3.0
	for side in [-1.0, 1.0]:
		var y: float = side * (hw - 1.0 + wheel_out)
		ci.draw_set_transform_matrix(base * Transform2D(0.0, Vector2(rear_x, y)))
		ci.draw_rect(Rect2(-1.5, -1.0, 3.0, 2.0), tire)
		ci.draw_rect(Rect2(-0.5, -0.5, 1.0, 1.0), rim)
		ci.draw_set_transform_matrix(base * Transform2D(steer_angle, Vector2(front_x, y)))
		ci.draw_rect(Rect2(-1.5, -1.0, 3.0, 2.0), tire)
		ci.draw_rect(Rect2(-0.5, -0.5, 1.0, 1.0), rim)
	ci.draw_set_transform_matrix(base)

	# Body outline (chamfered box) and fill.
	var ch := 2.0 if shape == "retro" else 1.0
	var outline := _box(hl, hw, ch)
	ci.draw_colored_polygon(outline, dark)
	ci.draw_colored_polygon(_box(hl - 0.5, hw - 0.5, ch), body)
	# Side shading: lit from the top of the screen in car space (left side).
	ci.draw_rect(Rect2(-hl + 1.0, hw - 1.5, L - 2.0, 1.0), dark)
	ci.draw_rect(Rect2(-hl + 2.0, -hw + 0.5, L - 4.0, 1.0), light)

	# Cabin: windscreen, roof, rear window. Proportions depend on the shape.
	var ws_x := hl - 6.0    # front edge of windscreen (rear side)
	var roof_len := 5.0
	match shape:
		"sport":
			ws_x = hl - 7.0
			roof_len = 4.0
		"coupe":
			ws_x = hl - 6.5
			roof_len = 4.5
		"retro":
			ws_x = hl - 5.0
			roof_len = 4.0
		"rally":
			roof_len = 6.0
		"wide":
			ws_x = hl - 6.5
	var glass := Color(GLASS, alpha)
	var glass_hi := Color(GLASS_HI, alpha)
	ci.draw_rect(Rect2(ws_x, -hw + 1.5, 2.0, W - 3.0), glass)
	ci.draw_rect(Rect2(ws_x + 1.0, -hw + 1.5, 1.0, 1.0), glass_hi)
	var roof := Rect2(ws_x - roof_len, -hw + 1.5, roof_len, W - 3.0)
	ci.draw_rect(roof, body.darkened(0.08))
	ci.draw_rect(Rect2(roof.position.x - 1.5, -hw + 1.5, 1.5, W - 3.0), glass)

	# Lights.
	var head := Color(HEAD, alpha)
	var tail := Color(TAIL_ON if braking else TAIL, alpha)
	ci.draw_rect(Rect2(hl - 1.0, -hw + 0.5, 1.0, 1.5), head)
	ci.draw_rect(Rect2(hl - 1.0, hw - 2.0, 1.0, 1.5), head)
	ci.draw_rect(Rect2(-hl, -hw + 0.5, 1.0, 1.5), tail)
	ci.draw_rect(Rect2(-hl, hw - 2.0, 1.0, 1.5), tail)

	_draw_decal(ci, decal, hl, hw, ws_x, roof, alpha, color)

	# Shape extras.
	var trim := Color(0.08, 0.08, 0.1, alpha)
	match shape:
		"sport", "coupe":
			ci.draw_rect(Rect2(-hl - 1.0, -hw, 1.5, W), trim)
		"rally":
			ci.draw_rect(Rect2(roof.position.x + 1.0, -hw + 1.5, 0.5, W - 3.0), Color(0.2, 0.2, 0.22, alpha))
			ci.draw_rect(Rect2(roof.position.x + 3.0, -hw + 1.5, 0.5, W - 3.0), Color(0.2, 0.2, 0.22, alpha))
			ci.draw_rect(Rect2(hl - 0.5, -1.5, 1.0, 3.0), Color(1.0, 1.0, 0.85, alpha))
		"retro":
			var chrome := Color(0.85, 0.86, 0.9, alpha)
			ci.draw_rect(Rect2(hl - 0.5, -hw + 1.0, 0.8, W - 2.0), chrome)
			ci.draw_rect(Rect2(-hl - 0.3, -hw + 1.0, 0.8, W - 2.0), chrome)
		"wide":
			ci.draw_rect(Rect2(-hl - 0.5, -hw - 0.5, 1.5, W + 1.0), trim)
	ci.draw_set_transform_matrix(Transform2D.IDENTITY)


static func _box(hl: float, hw: float, ch: float) -> PackedVector2Array:
	return PackedVector2Array([
		Vector2(-hl + ch, -hw), Vector2(hl - ch, -hw), Vector2(hl, -hw + ch), Vector2(hl, hw - ch),
		Vector2(hl - ch, hw), Vector2(-hl + ch, hw), Vector2(-hl, hw - ch), Vector2(-hl, -hw + ch),
	])


static func _draw_decal(ci: CanvasItem, decal: int, hl: float, hw: float, ws_x: float, roof: Rect2,
		alpha: float, body: Color) -> void:
	var accent := Color(1, 1, 1, alpha) if body.get_luminance() < 0.6 else Color(0.1, 0.1, 0.15, alpha)
	match decal:
		1:  # Stripes along the whole car
			ci.draw_rect(Rect2(-hl + 1.0, -1.0, hl * 2.0 - 2.0, 0.7), accent)
			ci.draw_rect(Rect2(-hl + 1.0, 0.4, hl * 2.0 - 2.0, 0.7), accent)
		2:  # Flames on the hood
			var hood_x := ws_x + 2.0
			var fl := Color(1.0, 0.55, 0.1, alpha)
			var fy := Color(1.0, 0.9, 0.2, alpha)
			ci.draw_colored_polygon(PackedVector2Array([
				Vector2(hood_x, -hw + 1.0), Vector2(hl - 1.0, -0.5), Vector2(hood_x, 1.0)]), fl)
			ci.draw_colored_polygon(PackedVector2Array([
				Vector2(hood_x, -1.0), Vector2(hl - 2.0, 0.5), Vector2(hood_x, hw - 1.0)]), fy)
		3:  # Race number roundel on the roof
			var c := roof.get_center()
			ci.draw_circle(c, 1.6, Color(1, 1, 1, alpha))
			ci.draw_rect(Rect2(c.x - 0.5, c.y - 1.0, 1.0, 2.0), Color(0.1, 0.1, 0.1, alpha))
		4:  # Checker on the hood
			var x0 := ws_x + 2.0
			var s := 1.0
			var yy := -hw + 1.0
			var row := 0
			while yy < hw - 1.0:
				var xx := x0 + (s if row % 2 == 1 else 0.0)
				while xx < hl - 1.0:
					ci.draw_rect(Rect2(xx, yy, s, s), Color(0.05, 0.05, 0.05, alpha))
					xx += s * 2.0
				yy += s
				row += 1
		5:  # Lightning bolt
			ci.draw_polyline(PackedVector2Array([
				Vector2(-hl + 2.0, -1.0), Vector2(-1.0, 0.8), Vector2(1.0, -0.8), Vector2(hl - 2.0, 1.0)]),
				Color(1.0, 0.9, 0.2, alpha), 1.0)
