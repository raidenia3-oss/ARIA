shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never;

uniform float time : hint_range(0.0, 100.0) = 0.0;
uniform vec3 color_a : source_color = vec3(0.486, 0.302, 1.0);
uniform vec3 color_b : source_color = vec3(0.0, 0.898, 1.0);
uniform bool domain_active = false;
uniform float domain_progress : hint_range(0.0, 1.0) = 0.0;

void vertex() {
	float pulse = 0.5 + 0.5 * sin(time * 4.0 + VERTEX.x * 2.0);
	VERTEX *= 1.0 + pulse * 0.3;
	if (domain_active) {
		float angle = time * 0.5 + VERTEX.x * 0.1;
		vec2 swirl = vec2(cos(angle), sin(angle)) * domain_progress * 0.5;
		VERTEX.xz += swirl;
	}
}

void fragment() {
	float dist = length(UV - vec2(0.5));
	float glow = 1.0 - smoothstep(0.0, 0.5, dist);
	vec3 color = mix(color_a, color_b, UV.y);
	float scan = 0.9 + 0.1 * sin(UV.y * 40.0 + time * 2.0);
	float intensity = glow * scan;
	if (domain_active) {
		intensity *= 1.0 + domain_progress * 2.0;
	}
	ALBEDO = color * intensity;
	EMISSION = color * intensity * 2.0;
	ALPHA = intensity;
}
