shader_type: spatial;
render_mode: spatial;

uniform vec4 base_color : source_color = vec4(0.22, 0.74, 0.98, 1.0);
uniform vec4 glow_color : source_color = vec4(0.0, 0.83, 1.0, 1.0);
uniform vec4 pulse_color : source_color = vec4(0.69, 0.40, 1.0, 1.0);
uniform float intensity : hint_range(0, 3) = 1.0;
uniform float particle_count : hint_range(4, 32) = 12.0;
uniform float time = 0.0;

void fragment() {
    float pulse = abs(sin(time * 2.0 * 3.14159 / 1.5));
    vec4 final_base = mix(base_color, pulse_color, pulse * 0.3 * intensity);
    ALBEDO = final_base.rgb;
    METALLIC = 0.0;
    ROUGHNESS = 0.3;
    EMISSION = glow_color.rgb * intensity * (1.0 + pulse * 0.5);
    EMISSION_ENERGY = intensity * 1.5;
}