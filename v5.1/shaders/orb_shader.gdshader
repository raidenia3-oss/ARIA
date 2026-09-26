shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never;

uniform sampler2D noise_texture : hint_black;
uniform float time : hint_range(0, 100);
uniform float intensity : hint_range(0, 5) = 1.0;
uniform vec3 base_color : source_color = vec3(0.22, 0.74, 0.98);
uniform vec3 glow_color : source_color = vec3(0.0, 0.83, 1.0);
uniform vec3 pulse_color : source_color = vec3(0.69, 0.40, 1.0);
uniform float particle_count : hint_range(1, 32) = 12.0;

varying vec3 v_normal;
varying vec3 v_world_pos;
varying float v_pulse;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

float fbm(vec2 p, int octaves) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 8; i++) {
        if (i >= octaves) break;
        value += amplitude * noise(p);
        p *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

vec3 get_sphere_normal(vec3 pos, float radius) {
    return normalize(pos) * radius;
}

void vertex() {
    v_normal = (MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz;
    v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    
    float pulse = abs(sin(time * 2.0 * 3.14159 / 1.5));
    v_pulse = pulse;
    
    float radius = 1.0 + pulse * 0.15 * intensity;
    VERTEX = normalize(VERTEX) * radius;
}

void fragment() {
    float ndotv = max(dot(normalize(v_normal), normalize(CAMERA_MATRIX[2].xyz)), 0.0);
    float fresnel = pow(1.0 - ndotv, 3.0);
    
    vec2 uv = vec2(atan(v_normal.z, v_normal.x) / (2.0 * 3.14159) + 0.5, 
                   asin(clamp(v_normal.y, -1.0, 1.0)) / 3.14159 + 0.5);
    
    float n = fbm(uv * 10.0 + time * 0.1, 4);
    float ring = sin(uv.y * 3.14159 * 8.0 + time * 2.0) * 0.5 + 0.5;
    
    vec3 color = mix(base_color, glow_color, fresnel);
    color += pulse_color * v_pulse * 0.5;
    color += vec3(n * 0.3) * intensity;
    color += vec3(ring * 0.2) * intensity;
    
    float alpha = fresnel * 0.8 + 0.2;
    alpha *= intensity;
    
    ALBEDO = color;
    EMISSION = color * 2.0;
    ALPHA = alpha;
}