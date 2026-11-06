shader_type canvas_item;
// Post-processing for the low-res game view (applied to the SubViewportContainer).
// Each graphics style (scripts/core/graphics_style.gd) sets these uniforms.

uniform vec2 source_size = vec2(480.0, 270.0);
uniform float saturation = 1.0;
uniform float contrast = 1.0;
uniform float brightness = 0.0;
uniform vec3 tint = vec3(1.0);
// 0: full colour, 1: four-shade handheld palette with dithering, 2: posterize
uniform int palette_mode = 0;
uniform vec3 pal0 : source_color = vec3(0.06, 0.22, 0.06);
uniform vec3 pal1 : source_color = vec3(0.19, 0.38, 0.19);
uniform vec3 pal2 : source_color = vec3(0.55, 0.67, 0.06);
uniform vec3 pal3 : source_color = vec3(0.61, 0.74, 0.06);
uniform float posterize_levels = 5.0;
uniform float scanlines = 0.0;
uniform float vignette = 0.0;
uniform float aberration = 0.0;

void fragment() {
	vec2 uv = UV;
	vec3 c;
	if (aberration > 0.0) {
		float o = aberration / source_size.x;
		c = vec3(texture(TEXTURE, uv + vec2(o, 0.0)).r, texture(TEXTURE, uv).g, texture(TEXTURE, uv - vec2(o, 0.0)).b);
	} else {
		c = texture(TEXTURE, uv).rgb;
	}
	c = (c - 0.5) * contrast + 0.5 + brightness;
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(vec3(l), c, saturation) * tint;
	vec2 px = floor(uv * source_size);
	if (palette_mode == 1) {
		float lum = clamp(dot(c, vec3(0.299, 0.587, 0.114)), 0.0, 1.0);
		float bayer = mod(px.x + px.y * 2.0, 4.0) / 4.0 - 0.375;
		lum = clamp(lum * 1.15 + bayer * 0.2, 0.0, 0.999);
		int i = int(floor(lum * 4.0));
		c = i == 0 ? pal0 : (i == 1 ? pal1 : (i == 2 ? pal2 : pal3));
	} else if (palette_mode == 2) {
		c = floor(c * posterize_levels + 0.5) / posterize_levels;
	}
	if (scanlines > 0.0) {
		// Darken the lower half of every source pixel row.
		float row = fract(uv.y * source_size.y);
		c *= row > 0.5 ? 1.0 - scanlines : 1.0;
	}
	if (vignette > 0.0) {
		vec2 d = uv - 0.5;
		c *= 1.0 - vignette * dot(d, d) * 2.2;
	}
	COLOR = vec4(clamp(c, 0.0, 1.0), 1.0);
}
