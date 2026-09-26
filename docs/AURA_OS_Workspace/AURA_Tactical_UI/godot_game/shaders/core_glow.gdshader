// Shader: Glow futurista para el núcleo de AURA
// Uso: Asignar a MeshInstance3D (Sphere) + PointLight3D

shader_type spatial;
render_mode blend_add, cull_back;

uniform vec3 color_a : source_color = vec3(0.0, 0.94, 1.0);   // Cyan neón
uniform vec3 color_b : source_color = vec3(0.3, 0.0, 1.0);    // Púrpura profundo
uniform float glow_intensity : hint_range(0.0, 5.0) = 1.8;
uniform float pulse_speed : hint_range(0.1, 10.0) = 2.0;
uniform float fresnel_power : hint_range(0.5, 10.0) = 3.0;

varying vec3 view_dir;
varying float fresnel;

void vertex() {
    vec4 world_pos = model_matrix * vec4(VERTEX, 1.0);
    view_dir = normalize(inverse(view_matrix) * vec4(0.0, 0.0, 0.0, 1.0) - world_pos.xyz);
    fresnel = pow(1.0 - abs(dot(NORMAL, view_dir)), fresnel_power);
}

void fragment() {
    float pulse = 0.7 + 0.3 * sin(TIME * pulse_speed);
    vec3 base = mix(color_a, color_b, 0.5 + 0.5 * sin(TIME * 0.6));
    vec3 col = base * glow_intensity * pulse;
    col += fresnel * color_a * glow_intensity * 0.8;
    ALPHA = 0.6 + 0.4 * fresnel;
    EMISSION = col * 2.0;
}
