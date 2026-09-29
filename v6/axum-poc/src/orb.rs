use std::time::{Duration, Instant};
use std::sync::{Mutex as StdMutex, OnceLock};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::f32::consts::PI;

use wgpu::util::DeviceExt;
use winit::{
    dpi::PhysicalSize,
    event::{Event, WindowEvent},
    event_loop::{ControlFlow, EventLoop, EventLoopBuilder},
    window::WindowBuilder,
};
use bytemuck::{Pod, Zeroable};

const PARTICLE_COUNT: usize = 12;
const FIBONACCI_COUNT: usize = 89;
const INFON_COUNT: usize = 34;
const BURST_COUNT: usize = 42;
const EVOLUTION_RINGS: usize = 3;

#[repr(C)]
#[derive(Pod, Zeroable, Copy, Clone)]
pub struct OrbUniforms {
    pub time: f32,
    pub breath: f32,
    pub pulse: f32,
    pub evolution_phase: i32,
    pub core_color: [f32; 4],
    pub glow_color: [f32; 4],
    pub eye_color: [f32; 4],
    pub fractal_color: [f32; 4],
    pub screen_size: [f32; 2],
    pub _pad: f32,
    pub _pad2: f32,
}

impl OrbUniforms {
    fn new() -> Self {
        Self {
            time: 0.0,
            breath: 1.0,
            pulse: 0.0,
            evolution_phase: 0,
            core_color: hex_to_rgba("#38bdf8"),
            glow_color: hex_to_rgba("#0284c7"),
            eye_color: hex_to_rgba("#60a5fa"),
            fractal_color: hex_to_rgba("#1e40af"),
            screen_size: [1280.0, 720.0],
            _pad: 0.0,
            _pad2: 0.0,
        }
    }
}

fn hex_byte(b: u8) -> u8 {
    match b {
        b'0'..=b'9' => b - b'0',
        b'a'..=b'f' => b - b'a' + 10,
        b'A'..=b'F' => b - b'A' + 10,
        _ => 0,
    }
}

fn hex_to_rgba(hex: &str) -> [f32; 4] {
    let bytes = hex.as_bytes();
    let r = (hex_byte(bytes[1]) * 16 + hex_byte(bytes[2])) as f32 / 255.0;
    let g = (hex_byte(bytes[3]) * 16 + hex_byte(bytes[4])) as f32 / 255.0;
    let b = (hex_byte(bytes[5]) * 16 + hex_byte(bytes[6])) as f32 / 255.0;
    [r, g, b, 1.0]
}

#[repr(C)]
#[derive(Pod, Zeroable, Copy, Clone)]
pub struct Particle {
    pub pos: [f32; 3],
    pub vel: [f32; 3],
    pub color: [f32; 4],
}

#[repr(C)]
#[derive(Pod, Zeroable, Copy, Clone)]
pub struct FractalVertex {
    pub pos: [f32; 3],
    pub normal: [f32; 3],
    pub uv: [f32; 2],
}

#[repr(C)]
#[derive(Pod, Zeroable, Copy, Clone)]
pub struct LayerConfig {
    pub radius: f32,
    pub opacity: f32,
    pub intensity: f32,
    pub speed: [f32; 3],
}

const LAYERS: [LayerConfig; 7] = [
    LayerConfig { radius: 0.5, opacity: 0.98, intensity: 0.55, speed: [0.1, 0.26, 0.04] },
    LayerConfig { radius: 0.6, opacity: 0.72, intensity: 0.85, speed: [-0.16, 0.2, 0.08] },
    LayerConfig { radius: 0.72, opacity: 0.52, intensity: 1.1, speed: [0.22, -0.18, -0.06] },
    LayerConfig { radius: 0.86, opacity: 0.38, intensity: 1.35, speed: [-0.12, 0.14, 0.1] },
    LayerConfig { radius: 1.02, opacity: 0.26, intensity: 1.6, speed: [0.18, -0.1, 0.05] },
    LayerConfig { radius: 1.2, opacity: 0.16, intensity: 1.85, speed: [-0.08, 0.12, -0.07] },
    LayerConfig { radius: 1.42, opacity: 0.1, intensity: 2.1, speed: [0.06, 0.08, 0.03] },
];

#[repr(C)]
#[derive(Clone, Copy, PartialEq)]
pub enum OrbPhase {
    Idle,
    Thinking,
    Responding,
    Listening,
    Wisdom,
}

impl Default for OrbPhase {
    fn default() -> Self { OrbPhase::Idle }
}

#[repr(C)]
#[derive(Clone, Copy, PartialEq)]
#[allow(dead_code)]
pub struct PhaseColors {
    pub core: [f32; 4],
    pub glow: [f32; 4],
    pub fractal: [f32; 4],
    pub eye: [f32; 4],
    pub infon: [f32; 4],
}

fn phase_colors() -> [PhaseColors; 5] {
    [
        PhaseColors { core: hex_to_rgba("#38bdf8"), glow: hex_to_rgba("#0284c7"), fractal: hex_to_rgba("#1e40af"), eye: hex_to_rgba("#60a5fa"), infon: hex_to_rgba("#38bdf8") },
        PhaseColors { core: hex_to_rgba("#f59e0b"), glow: hex_to_rgba("#b45309"), fractal: hex_to_rgba("#7c2d12"), eye: hex_to_rgba("#fbbf24"), infon: hex_to_rgba("#f59e0b") },
        PhaseColors { core: hex_to_rgba("#00d4ff"), glow: hex_to_rgba("#0e7490"), fractal: hex_to_rgba("#083344"), eye: hex_to_rgba("#67e8f4"), infon: hex_to_rgba("#00d4ff") },
        PhaseColors { core: hex_to_rgba("#b066ff"), glow: hex_to_rgba("#7c3aed"), fractal: hex_to_rgba("#311b92"), eye: hex_to_rgba("#c49afe"), infon: hex_to_rgba("#b066ff") },
        PhaseColors { core: hex_to_rgba("#ffffff"), glow: hex_to_rgba("#a78bfa"), fractal: hex_to_rgba("#4c1d99"), eye: hex_to_rgba("#ffffff"), infon: hex_to_rgba("#fbbf24") },
    ]
}

const VERTEX_SHADER: &str = r#"
@vertex
fn vs_main(
    @builtin(vertex_index) vertexIndex: u32,
) -> @builtin(position) vec4<f32> {
    var pos = array<vec2<f32>, 6>(
        vec2<f32>(-1.0, 1.0),
        vec2<f32>(-1.0, -1.0),
        vec2<f32>(1.0, -1.0),
        vec2<f32>(-1.0, 1.0),
        vec2<f32>(1.0, -1.0),
        vec2<f32>(1.0, 1.0),
    );
    let p = pos[vertexIndex];
    return vec4<f32>(p, 0.0, 1.0);
}
"#;

const FRAGMENT_SHADER: &str = r#"
struct Uniforms {
    time: f32,
    breath: f32,
    pulse: f32,
    evolution_phase: i32,
    core_color: vec4<f32>,
    glow_color: vec4<f32>,
    eye_color: vec4<f32>,
    fractal_color: vec4<f32>,
    screen_size: vec2<f32>,
    _pad: f32,
    _pad2: f32,
};
@group(0) @binding(0) var<uniform> u: Uniforms;

fn sdSphere(p: vec3<f32>, s: f32) -> f32 {
    return length(p) - s;
}

fn opSmoothUnion(p: vec3<f32>, s: f32) -> f32 {
    let r1 = sdSphere(p, s);
    let r2 = sdSphere(p, s * 0.6);
    let k = 0.3;
    let h = max(k - abs(r1 - r2), 0.0) / k;
    return min(r1, r2) - h * h * k * 0.5;
}

fn hash11(p: f32) -> f32 {
    return fract(sin(p * 12.9898) * 43758.5453);
}

fn hash22(p: vec2<f32>) -> vec2<f32> {
    var q = vec2<f32>(dot(p, vec2<f32>(127.1, 311.7)), dot(p, vec2<f32>(269.5, 183.3)));
    return fract(sin(q) * 43758.5453);
}

fn gold_noise(p: vec2<f32>, seed: f32) -> f32 {
    return fract(sin(dot(p, vec2<f32>(12.9898, 78.233)) + seed) * 43758.5453);
}

@fragment
fn fs_main(@builtin(position) coord: vec4<f32>) -> @location(0) vec4<f32> {
    let uv = coord.xy / u.screen_size.xy;
    let ndc = uv * 2.0 - 1.0;

    let center = vec2<f32>(0.0, 0.0);
    let p = ndc;

    let r = length(p);
    let theta = atan2(p.y, p.x);

    let phase_idx = u.evolution_phase;

    // === Core breathing sphere ===
    let breath_scale = 1.0 + sin(u.time * (3.14159 * 2.0 / 1.5)) * 0.035;
    let spiral = sin(theta * 8.0 - u.time * 0.5 - r * 12.0) * 0.5 + 0.5;
    let layer_intensity = 0.92 + 0.08 * sin(u.time * (3.14159 * 2.0 / 1.5) + theta * 3.0);
    let fres = pow(max(0.0, 1.0 - r), 2.2);

    let fractal = spiral * breath_scale * fres;

    // === Multi-layer glow rings ===
    let ring_glow = exp(-r * 3.0) * (0.5 + 0.5 * sin(u.time * 4.0 + theta * 20.0));

    // === Fibonacci particle field ===
    var particle_mask: f32 = 0.0;
    let phi_gold = 2.39996362874195264437;
    for (var i: i32 = 0; i < 89; i = i + 1) {
        let fi = f32(i);
        let lat = acos(1.0 - 2.0 * (fi / 89.0));
        let lon = fi * phi_gold;
        let px = sin(lat) * cos(lon);
        let py = sin(lat) * sin(lon);

        let proj_x = px * sqrt(1.0 - py * py * 0.5);
        let proj_y = py * 0.866;

        let pd = length(vec2<f32>(proj_x, proj_y) * 0.7 - p);
        let sz = (70.0 - r * 70.0) / (pd * 8.0 + 0.5);
        let sz_clamped = max(sz, 0.0);
        particle_mask = particle_mask + sz_clamped;
    }

    // === Burst rays ===
    let burst = pow(max(0.0, sin(theta * 24.0 + u.time * 8.0)), 8.0);
    let burst2 = pow(max(0.0, sin(theta * 12.0 - u.time * 5.0)), 12.0);
    let burst_total = (burst + burst2) * (1.0 - r) * 0.3;

    // === Energy field ===
    let energy = exp(-r * 2.0) * 0.8 + ring_glow * 0.4 + burst_total;

    let core = u.core_color;
    let glow = u.glow_color;
    let eye = u.eye_color;
    let fractal_c = u.fractal_color;

    // === Composite layers ===
    let core_bright = core * (0.4 + fractal * 0.3 + energy * 0.3);
    let glow_add = glow * (ring_glow * 0.3 + energy * 0.5);
    let particle_add = eye * (particle_mask * 0.003);

    let col = core_bright + glow_add + particle_add;
    let alpha = clamp(
        fractal * (0.3 + 0.7 * fres) * u.pulse * 0.8
        + energy * 0.5 * (1.0 - r)
        + burst_total * 0.3
        + particle_mask * 0.002
        + 0.15,
        0.0,
        0.85
    );

    // === Chromatic aberration glow ===
    let aberration = vec3<f32>(0.02, -0.01, 0.03) * (1.0 - r) * fres;
    let final_color = col.rgb + aberration;
    let final_alpha = alpha * 0.92;

    return vec4<f32>(final_color, final_alpha);
}
"#;

fn radial_gradient_texture(size: usize, intensity: f32) -> Vec<u8> {
    let mut data = vec![0u8; size * size * 4];
    let center = (size as f32 / 2.0) as usize;
    for y in 0..size {
        for x in 0..size {
            let dx = x as f32 - center as f32;
            let dy = y as f32 - center as f32;
            let dist = (dx * dx + dy * dy).sqrt();
            let max_dist = center as f32;
            let alpha = ((1.0 - dist / max_dist).max(0.0) * intensity * 255.0) as u8;
            let idx = (y * size + x) * 4;
            data[idx] = 255;
            data[idx + 1] = 255;
            data[idx + 2] = 255;
            data[idx + 3] = alpha;
        }
    }
    data
}

fn create_sphere_vertices(radius: f32, segments: usize) -> Vec<f32> {
    let mut vertices = Vec::new();
    for i in 0..=segments {
        let phi = (i as f32) * PI / (segments as f32);
        for j in 0..=segments {
            let theta = (j as f32) * 2.0 * PI / (segments as f32);
            let x = radius * (phi.sin() * theta.cos());
            let y = radius * phi.cos();
            let z = radius * (phi.sin() * theta.sin());
            let len = (x * x + y * y + z * z).sqrt();
            if len > 0.0 {
                vertices.extend_from_slice(&[x / len, y / len, z / len]);
            }
        }
    }
    vertices
}

fn create_ring_vertices(inner: f32, outer: f32, segments: usize) -> Vec<f32> {
    let mut vertices = Vec::new();
    for i in 0..=segments {
        let angle = (i as f32) * 2.0 * PI / (segments as f32);
        let x = angle.cos();
        let z = angle.sin();
        vertices.extend_from_slice(&[x * inner, 0.0, z * inner]);
        vertices.extend_from_slice(&[x * outer, 0.0, z * outer]);
    }
    vertices
}

pub struct OrbScene {
    pub phase: OrbPhase,
    pub uniforms: OrbUniforms,
    pub animated: bool,
    pub last_update: Instant,
    pub layer_rotations: Vec<[f32; 3]>,
    pub particle_offsets: Vec<f32>,
    pub started: bool,
}

impl OrbScene {
    pub fn new(screen_size: (f32, f32)) -> Self {
        let mut uniforms = OrbUniforms::new();
        uniforms.screen_size = [screen_size.0, screen_size.1];
        uniforms.pulse = 1.0;
        
        Self {
            phase: OrbPhase::Idle,
            uniforms,
            animated: true,
            last_update: Instant::now(),
            layer_rotations: LAYERS.iter().map(|_| [0.0f32, 0.0, 0.0]).collect(),
            particle_offsets: (0..PARTICLE_COUNT).map(|i| (i as f32 / PARTICLE_COUNT as f32) * 2.0 * PI).collect(),
            started: false,
        }
    }

    pub fn set_phase(&mut self, phase: OrbPhase) {
        if phase == self.phase { return; }
        self.phase = phase;
        let colors = phase_colors()[phase as usize];
        self.uniforms.core_color = colors.core;
        self.uniforms.glow_color = colors.glow;
        self.uniforms.eye_color = colors.eye;
        self.uniforms.fractal_color = colors.fractal;
    }

    pub fn update(&mut self, dt: f32, t: f32) {
        let motion: f32 = if self.animated { 1.0 } else { 0.0 };
        self.uniforms.time = t;
        self.uniforms.breath = 1.0 + ((t / 1.5) * 2.0 * PI).sin() * 0.035 * motion;
        self.uniforms.pulse = 0.7 + 0.3 * ((t * 1.3).sin()) * motion;
        self.uniforms.evolution_phase = match self.phase {
            OrbPhase::Idle => 0,
            OrbPhase::Thinking => 1,
            OrbPhase::Responding => 2,
            OrbPhase::Listening => 3,
            OrbPhase::Wisdom => 4,
        };

        for (i, layer) in LAYERS.iter().enumerate() {
            self.layer_rotations[i][0] += layer.speed[0] * dt * motion;
            self.layer_rotations[i][1] += layer.speed[1] * dt * motion;
            self.layer_rotations[i][2] += layer.speed[2] * dt * motion;
        }

        for offset in &mut self.particle_offsets {
            *offset += dt * 0.35 * motion;
        }
    }

    pub fn render_state(&self) -> Option<String> {
        match self.phase {
            OrbPhase::Idle => Some("idle".to_string()),
            OrbPhase::Thinking => Some("thinking".to_string()),
            OrbPhase::Responding => Some("responding".to_string()),
            OrbPhase::Listening => Some("listening".to_string()),
            OrbPhase::Wisdom => Some("wisdom".to_string()),
        }
    }
}

pub struct OrbRenderer {
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    surface_config: wgpu::SurfaceConfiguration,
    render_pipeline: wgpu::RenderPipeline,
    uniform_buffer: wgpu::Buffer,
    uniform_bind_group: wgpu::BindGroup,
    texture: wgpu::Texture,
    sampler: wgpu::Sampler,
    depth_texture: wgpu::Texture,
    scene: OrbScene,
}

impl OrbRenderer {
    pub async fn new(window: &winit::window::Window, scene: OrbScene) -> Self {
        let size = window.inner_size();
        let instance = wgpu::Instance::default();
        let surface = instance.create_surface(window).unwrap();
        let surface = unsafe { std::mem::transmute::<wgpu::Surface<'_>, wgpu::Surface<'static>>(surface) };
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                compatible_surface: Some(&surface),
                force_fallback_adapter: false,
            })
            .await
            .unwrap();

        let (device, queue) = adapter
            .request_device(
                &wgpu::DeviceDescriptor {
                    label: Some("ARIA Orb GPU"),
                    required_features: wgpu::Features::empty(),
                    required_limits: wgpu::Limits::default(),
                    memory_hints: wgpu::MemoryHints::Performance,
                },
                None,
            )
            .await
            .unwrap();

        let surface_caps = surface.get_capabilities(&adapter);
        let surface_format = surface_caps
            .formats
            .iter()
            .copied()
            .find(|f| f.is_srgb())
            .unwrap_or(surface_caps.formats[0]);

        let surface_config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: surface_format,
            width: size.width,
            height: size.height,
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
            present_mode: surface_caps.present_modes[0],
            alpha_mode: surface_caps.alpha_modes[0],
        };
        surface.configure(&device, &surface_config);

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Orb Shader"),
            source: wgpu::ShaderSource::Wgsl(std::borrow::Cow::Borrowed(FRAGMENT_SHADER)),
        });

        let vertex_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Orb Vertex Shader"),
            source: wgpu::ShaderSource::Wgsl(std::borrow::Cow::Borrowed(VERTEX_SHADER)),
        });

        let uniform_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Orb Uniforms"),
            contents: bytemuck::bytes_of(&scene.uniforms),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });

        let particle_texture = radial_gradient_texture(64, 1.0);
        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Particle Texture"),
            size: wgpu::Extent3d {
                width: 64,
                height: 64,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST | wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });

        let texture_view = texture.create_view(&wgpu::TextureViewDescriptor::default());

        let texture_size = wgpu::Extent3d {
            width: 64,
            height: 64,
            depth_or_array_layers: 1,
        };

        queue.write_texture(
            wgpu::ImageCopyTexture {
                texture: &texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            &particle_texture,
            wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(64 * 4),
                rows_per_image: Some(64),
            },
            texture_size,
        );

        let sampler = device.create_sampler(&wgpu::SamplerDescriptor {
            label: Some("Orb Sampler"),
            mag_filter: wgpu::FilterMode::Linear,
            min_filter: wgpu::FilterMode::Linear,
            mipmap_filter: wgpu::FilterMode::Linear,
            address_mode_u: wgpu::AddressMode::ClampToEdge,
            address_mode_v: wgpu::AddressMode::ClampToEdge,
            address_mode_w: wgpu::AddressMode::ClampToEdge,
            ..Default::default()
        });

        let uniform_bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("Orb Bind Group Layout"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 2,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });

        let uniform_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Orb Bind Group"),
            layout: &uniform_bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: uniform_buffer.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::TextureView(&texture_view),
                },
                wgpu::BindGroupEntry {
                    binding: 2,
                    resource: wgpu::BindingResource::Sampler(&sampler),
                },
            ],
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Orb Pipeline Layout"),
            bind_group_layouts: &[&uniform_bind_group_layout],
            push_constant_ranges: &[],
        });

        let render_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Orb Render Pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &vertex_shader,
                entry_point: "vs_main",
                buffers: &[],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: "fs_main",
                targets: &[Some(wgpu::ColorTargetState {
                    format: surface_format,
                    blend: Some(wgpu::BlendState {
                        color: wgpu::BlendComponent {
                            src_factor: wgpu::BlendFactor::SrcAlpha,
                            dst_factor: wgpu::BlendFactor::OneMinusSrcAlpha,
                            operation: wgpu::BlendOperation::Add,
                        },
                        alpha: wgpu::BlendComponent {
                            src_factor: wgpu::BlendFactor::One,
                            dst_factor: wgpu::BlendFactor::OneMinusSrcAlpha,
                            operation: wgpu::BlendOperation::Add,
                        },
                    }),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: Default::default(),
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                strip_index_format: None,
                front_face: wgpu::FrontFace::Ccw,
                cull_mode: None,
                unclipped_depth: false,
                polygon_mode: wgpu::PolygonMode::Fill,
                conservative: false,
            },
            depth_stencil: None,
            multisample: wgpu::MultisampleState {
                count: 1,
                mask: !0,
                alpha_to_coverage_enabled: false,
            },
            multiview: None,
            cache: None,
        });

        let depth_texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Depth Texture"),
            size: wgpu::Extent3d {
                width: size.width,
                height: size.height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth24Plus,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });

        Self {
            surface,
            device,
            queue,
            surface_config,
            render_pipeline,
            uniform_buffer,
            uniform_bind_group,
            texture,
            sampler,
            depth_texture,
            scene,
        }
    }

    pub fn resize(&mut self, new_size: PhysicalSize<u32>) {
        if new_size.width > 0 && new_size.height > 0 {
            self.surface_config.width = new_size.width;
            self.surface_config.height = new_size.height;
            self.surface.configure(&self.device, &self.surface_config);
            self.depth_texture = self.device.create_texture(&wgpu::TextureDescriptor {
                label: Some("Depth Texture"),
                size: wgpu::Extent3d {
                    width: new_size.width,
                    height: new_size.height,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Depth24Plus,
                usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
                view_formats: &[],
            });
        }
    }

    pub fn update(&mut self, dt: f32, t: f32) {
        self.scene.update(dt, t);
        self.queue.write_buffer(&self.uniform_buffer, 0, bytemuck::bytes_of(&self.scene.uniforms));
    }

    pub fn render(&mut self, window: &winit::window::Window) -> Result<(), wgpu::SurfaceError> {
        let output = self.surface.get_current_texture()?;
        let view = output
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());

        let mut encoder = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor {
            label: Some("Orb Render Encoder"),
        });

        {
            let mut render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("Orb Render Pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.0,
                            g: 0.0,
                            b: 0.0,
                            a: 0.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                occlusion_query_set: None,
                timestamp_writes: None,
            });

            render_pass.set_pipeline(&self.render_pipeline);
            render_pass.set_bind_group(0, &self.uniform_bind_group, &[]);
            render_pass.draw(0..6, 0..1);
        }

        self.queue.submit(std::iter::once(encoder.finish()));
        output.present();

        Ok(())
    }

    pub fn get_scene(&self) -> &OrbScene {
        &self.scene
    }

    pub fn get_scene_mut(&mut self) -> &mut OrbScene {
        &mut self.scene
    }
}

/// True while an orb window thread is alive, so `/api/orb/start` cannot spawn
/// two event loops (winit panics if two Windows message loops exist).
static ORB_THREAD_ALIVE: AtomicBool = AtomicBool::new(false);

/// Set once the native window exists and rendering has started.
static ORB_READY: AtomicBool = AtomicBool::new(false);

/// Last orb failure, surfaced through `/api/orb/state`.
static ORB_LAST_ERROR: OnceLock<StdMutex<Option<String>>> = OnceLock::new();

/// Builds the winit event loop in a thread-safe way.
///
/// winit's `EventLoop::new()` panics on Windows when it is not created on the
/// main thread, so every path goes through this builder instead. On Windows the
/// loop is explicitly marked as "any thread", which downgrades that check to a
/// debug-only warning and lets the orb live on its own background thread while
/// the HTTP server keeps running.
fn build_event_loop() -> Result<EventLoop<()>, winit::error::EventLoopError> {
    let mut builder = EventLoopBuilder::<()>::with_user_event();

    #[cfg(target_os = "windows")]
    {
        use winit::platform::windows::EventLoopBuilderExtWindows;
        builder.with_any_thread(true);
    }

    #[cfg(not(target_os = "windows"))]
    let _ = &mut builder;

    builder.build()
}

/// Spawns the native orb window on a background thread and waits briefly for the
/// window to come up.
///
/// Returns `Err` when the window thread fails to start. winit can only build
/// one `EventLoop` per process, so restarting after `/api/orb/stop` requires a
/// process restart; that case is reported as a clean error instead of a panic.
/// The orb is optional visual feedback: a failure here never affects the HTTP
/// server.
pub fn spawn_orb_window() -> Result<(), String> {
    if ORB_THREAD_ALIVE.swap(true, Ordering::SeqCst) {
        return Err("orb window is already running".to_string());
    }

    *orb_last_error().lock().unwrap() = None;

    // The event loop exits as soon as this flag is false, so it must be set
    // before the window thread starts drawing.
    crate::daemon::orb_running().store(true, Ordering::SeqCst);

    let stop_flag = Arc::new(AtomicBool::new(true));
    std::thread::Builder::new()
        .name("aria-orb".to_string())
        .spawn(move || {
            // A renderer failure must never take down the process or the HTTP
            // server, so the window thread is isolated from unwinding out.
            let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                run_orb_window(stop_flag);
            }));
            if outcome.is_err() {
                *orb_last_error().lock().unwrap() =
                    Some("renderer panicked while drawing the orb".to_string());
                eprintln!("Orb window thread ended after an internal renderer error");
            }
        })
        .map_err(|e| {
            ORB_THREAD_ALIVE.store(false, Ordering::SeqCst);
            crate::daemon::orb_running().store(false, Ordering::SeqCst);
            format!("failed to spawn orb thread: {}", e)
        })?;

    // Wait for the window to be built so the API can report a real result
    // instead of optimistically claiming success.
    let deadline = Instant::now() + Duration::from_millis(2000);
    loop {
        if let Some(err) = orb_last_error().lock().unwrap().clone() {
            crate::daemon::orb_running().store(false, Ordering::SeqCst);
            return Err(err);
        }
        if ORB_READY.load(Ordering::SeqCst) {
            return Ok(());
        }
        if Instant::now() >= deadline {
            if ORB_THREAD_ALIVE.load(Ordering::SeqCst) {
                return Ok(());
            }
            crate::daemon::orb_running().store(false, Ordering::SeqCst);
            return Err("orb window thread exited before the window was created".to_string());
        }
        std::thread::sleep(Duration::from_millis(20));
    }
}

/// Whether an orb window thread is currently alive.
pub fn orb_window_alive() -> bool {
    ORB_THREAD_ALIVE.load(Ordering::SeqCst)
}

/// Last error raised by the orb window thread, if any.
pub fn orb_last_error() -> &'static StdMutex<Option<String>> {
    ORB_LAST_ERROR.get_or_init(|| StdMutex::new(None))
}

/// Clears the orb liveness flags when the window thread finishes, including
/// when it unwinds out of a panic, so `/api/orb/start` stays usable.
struct OrbThreadGuard;

impl Drop for OrbThreadGuard {
    fn drop(&mut self) {
        crate::daemon::orb_running().store(false, Ordering::SeqCst);
        ORB_READY.store(false, Ordering::SeqCst);
        ORB_THREAD_ALIVE.store(false, Ordering::SeqCst);
    }
}

/// Runs the orb window on the current thread. Prefer [`spawn_orb_window`],
/// which handles thread bookkeeping. `keep_running` is kept for API
/// compatibility; the live stop signal is `daemon::orb_running()`.
pub fn run_orb_window(_keep_running: Arc<AtomicBool>) {
    let _guard = OrbThreadGuard;
    let event_loop = match build_event_loop() {
        Ok(el) => el,
        Err(e) => {
            let msg = format!("event loop unavailable: {}", e);
            eprintln!("Orb not started: {}", msg);
            *orb_last_error().lock().unwrap() = Some(msg);
            return;
        }
    };

    let window = match WindowBuilder::new()
        .with_title("ARIA OS")
        .with_inner_size(PhysicalSize::new(600, 600))
        .with_resizable(false)
        .with_decorations(false)
        .with_transparent(true)
        .build(&event_loop)
    {
        Ok(w) => w,
        Err(e) => {
            let msg = format!("window creation failed: {}", e);
            eprintln!("Orb not started: {}", msg);
            *orb_last_error().lock().unwrap() = Some(msg);
            return;
        }
    };

    let win = Arc::new(window);
    let scene = OrbScene::new((600.0, 600.0));
    let mut renderer = pollster::block_on(OrbRenderer::new(&win, scene));
    ORB_READY.store(true, Ordering::SeqCst);

    let mut last_frame = Instant::now();

    if let Err(e) = event_loop.run(move |event, elwt| {
        elwt.set_control_flow(ControlFlow::Poll);

        match event {
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => {
                elwt.exit();
            }
            Event::AboutToWait => {
                let now = Instant::now();
                let dt = now.duration_since(last_frame).as_secs_f32().min(0.05);
                let t = now.elapsed().as_secs_f32();
                last_frame = now;

                // Poll phase from shared state to sync orb behavior
                {
                    let phase_guard = crate::daemon::orb_phase();
                    let phase = *phase_guard.lock().unwrap();
                    let scene = renderer.get_scene_mut();
                    if scene.phase != phase {
                        scene.set_phase(phase);
                    }
                }

                renderer.update(dt, t);
                match renderer.render(&win) {
                    Ok(_) => {}
                    Err(wgpu::SurfaceError::Lost) => renderer.resize(win.inner_size()),
                    Err(wgpu::SurfaceError::OutOfMemory) => elwt.exit(),
                    Err(e) => eprintln!("Render error: {:?}", e),
                }

                if !crate::daemon::orb_running().load(Ordering::SeqCst) {
                    elwt.exit();
                }
            }
            _ => {}
        }
    }) {
        eprintln!("Orb event loop ended: {}", e);
    }
}
