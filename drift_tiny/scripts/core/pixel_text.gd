class_name PixelText
extends RefCounted
## Tiny 3x5 bitmap font for text inside the low-resolution game world
## (player tags above cars, billboard letters). One glyph = 15 bits, row by row.

const GLYPHS := {
	"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
	"4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001010010010",
	"8": "111101111101111", "9": "111101111001111",
	"A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
	"E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
	"I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
	"M": "101111111101101", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
	"Q": "010101101110011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
	"U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
	"Y": "101101010010010", "Z": "111001010100111", "-": "000000111000000", "!": "010010010000010",
	".": "000000000000010", ":": "000010000010000", "+": "000010111010000", " ": "000000000000000",
}


static func width_of(text: String, scale := 1.0) -> float:
	return (text.length() * 4 - 1) * scale


## Draws text with its top-left corner at pos. Shadow adds a dark copy 1px down.
static func draw(ci: CanvasItem, pos: Vector2, text: String, color: Color, scale := 1.0, shadow := true) -> void:
	if shadow:
		_draw_raw(ci, pos + Vector2(0, scale), text, Color(0, 0, 0, color.a * 0.7), scale)
	_draw_raw(ci, pos, text, color, scale)


static func _draw_raw(ci: CanvasItem, pos: Vector2, text: String, color: Color, scale: float) -> void:
	var x := pos.x
	for ch in text.to_upper():
		var g: String = GLYPHS.get(ch, GLYPHS["-"])
		for i in 15:
			if g[i] == "1":
				ci.draw_rect(Rect2(x + (i % 3) * scale, pos.y + (i / 3) * scale, scale, scale), color)
		x += 4.0 * scale


static func draw_centered(ci: CanvasItem, center: Vector2, text: String, color: Color, scale := 1.0) -> void:
	draw(ci, center - Vector2(width_of(text, scale) * 0.5, 2.5 * scale), text, color, scale)
