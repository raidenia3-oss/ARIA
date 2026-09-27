shader_type: spatial;
render_mode: spatial;

uniform vec4 particle_color : source_color = vec4(0.22, 0.74, 0.98, 1.0);
uniform vec4 trail_color : source_color = vec4(0.69, 0.40, 1.0, 1.0);
uniform float orbit_radius = 2.5;
uniform float orbit_speed = 0.8;
uniform float particle_lifetime = 2.0;
uniform float time = 0.0;

void vertex() {
    float angle = time * orbit_speed + POSITION.x * 6.28;
    float radius = orbit_radius + sin(time * 2.0 + POSITION.y * 3.14) * 0.5;
    POSITION.x = cos(angle) * radius;
    POSITION.y = sin(angle) * radius;
    float alpha = 1.0 - (TIME / particle_lifetime);
    COLOR = vec4(particle_color.rgb, alpha * 0.8);
}

void fragment() {
    ALBEDO = COLOR.rgb;
    METALLIC = 0.5;
    ROUGHNESS = 0.4;
    EMISSION = trail_color.rgb * COLOR.a * 0.5;
}