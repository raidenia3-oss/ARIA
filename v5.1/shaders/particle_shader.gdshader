shader_type particles;
render_mode unshaded, blend_add, depth_draw_never;

uniform float time : hint_range(0, 100);
uniform float particle_lifetime : hint_range(0.5, 5.0) = 2.0;
uniform vec3 particle_color : source_color = vec3(0.22, 0.74, 0.98);
uniform vec3 trail_color : source_color = vec3(0.69, 0.40, 1.0);
uniform float orbit_radius : hint_range(1.0, 5.0) = 2.5;
uniform float orbit_speed : hint_range(0.1, 3.0) = 0.8;

void start() {
    float index = float(INDEX);
    float count = float(NUMBER);
    float angle = (index / count) * 2.0 * 3.14159;
    float phase = hash(vec2(index, 13.7)) * 2.0 * 3.14159;
    
    VELOCITY = vec3(0.0);
    TRANSFORM[3].xyz = vec3(
        cos(angle + phase) * orbit_radius,
        (hash(vec2(index, 7.3)) - 0.5) * 0.5,
        sin(angle + phase) * orbit_radius
    );
    
    CUSTOM = vec4(angle, phase, orbit_speed, hash(vec2(index, 42.1)));
}

void process() {
    float angle = CUSTOM.x + CUSTOM.z * time + CUSTOM.y;
    float radius = orbit_radius + sin(time * 0.5 + CUSTOM.y) * 0.3;
    float height = sin(time * 0.7 + CUSTOM.y * 2.0) * 0.4;
    
    TRANSFORM[3].xyz = vec3(
        cos(angle) * radius,
        height,
        sin(angle) * radius
    );
    
    float life_ratio = 1.0 - (TIME / particle_lifetime);
    float size = mix(0.15, 0.02, 1.0 - life_ratio);
    
    TRANSFORM[0].xyz *= size;
    TRANSFORM[1].xyz *= size;
    TRANSFORM[2].xyz *= size;
    
    vec3 color = mix(particle_color, trail_color, sin(time * 2.0 + CUSTOM.y) * 0.5 + 0.5);
    COLOR = vec4(color, life_ratio * 0.8);
    
    if (TIME > particle_lifetime) {
        RESTART = true;
        CUSTOM.w = hash(vec2(CUSTOM.w, 17.3));
    }
}

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}