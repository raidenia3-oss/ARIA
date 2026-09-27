using Godot;
using System;

namespace ARIA.Orb
{
    [GlobalClass]
    [Tool]
    public partial class OrbVisual3D : Node3D
    {
        [Export] public float PulseSpeed { get; set; } = 1.0f;
        [Export] public float Intensity { get; set; } = 1.0f;
        [Export] public int ParticleCount { get; set; } = 12;
        [Export] public Color BaseColor { get; set; } = new Color(0.22f, 0.74f, 0.98f);
        [Export] public Color GlowColor { get; set; } = new Color(0.0f, 0.83f, 1.0f);
        [Export] public Color PulseColor { get; set; } = new Color(0.69f, 0.40f, 1.0f);
        [Export] public Color ParticleColor { get; set; } = new Color(0.22f, 0.74f, 0.98f);
        [Export] public Color TrailColor { get; set; } = new Color(0.69f, 0.40f, 1.0f);

        private MeshInstance3D _coreMesh;
        private GPUParticles3D _orbitParticles;
        private GPUParticles3D _burstParticles;
        private OmniLight3D _coreLight;
        private float _pulseTime = 0f;
        private float _burstTimer = 0f;
        private RandomNumberGenerator _rng = new();

        public override void _Ready()
        {
            SetupCoreMesh();
            SetupOrbitParticles();
            SetupBurstParticles();
            SetupCoreLight();
            
            _rng.Randomize();
        }

        private void SetupCoreMesh()
        {
            _coreMesh = new MeshInstance3D();
            var sphereMesh = new SphereMesh();
            sphereMesh.Radius = 1.0f;
            sphereMesh.Height = 2.0f;
            sphereMesh.RadialSegments = 64;
            sphereMesh.Rings = 32;
            _coreMesh.Mesh = sphereMesh;

            var shader = GD.Load<Shader>("res://assets/shaders/orb_shader.gdshader");
            var material = new ShaderMaterial();
            material.Shader = shader;
            material.SetShaderParameter("base_color", BaseColor);
            material.SetShaderParameter("glow_color", GlowColor);
            material.SetShaderParameter("pulse_color", PulseColor);
            material.SetShaderParameter("intensity", Intensity);
            material.SetShaderParameter("particle_count", ParticleCount);
            _coreMesh.MaterialOverride = material;

            AddChild(_coreMesh);
        }

        private void SetupOrbitParticles()
        {
            _orbitParticles = new GPUParticles3D();
            _orbitParticles.Amount = ParticleCount;
            _orbitParticles.Lifetime = 10.0f;
            _orbitParticles.OneShot = false;
            _orbitParticles.ProcessMaterial = new ShaderMaterial();
            
            var particleShader = GD.Load<Shader>("res://assets/shaders/particle_shader.gdshader");
            (_orbitParticles.ProcessMaterial as ShaderMaterial).Shader = particleShader;
            (_orbitParticles.ProcessMaterial as ShaderMaterial).SetShaderParameter("particle_color", ParticleColor);
            (_orbitParticles.ProcessMaterial as ShaderMaterial).SetShaderParameter("trail_color", TrailColor);
            (_orbitParticles.ProcessMaterial as ShaderMaterial).SetShaderParameter("orbit_radius", 2.5f);
            (_orbitParticles.ProcessMaterial as ShaderMaterial).SetShaderParameter("orbit_speed", 0.8f);
            (_orbitParticles.ProcessMaterial as ShaderMaterial).SetShaderParameter("particle_lifetime", 2.0f);

            AddChild(_orbitParticles);
        }

        private void SetupBurstParticles()
        {
            _burstParticles = new GPUParticles3D();
            _burstParticles.Amount = 32;
            _burstParticles.Lifetime = 1.5f;
            _burstParticles.OneShot = true;
            _burstParticles.Explosiveness = 1.0f;
            _burstParticles.Spread = (float)Math.PI;
            _burstParticles.InitialVelocity = 5.0f;
            _burstParticles.Gravity = new Vector3(0, -2.0f, 0);
            _burstParticles.Scale = 0.1f;
            _burstParticles.ScaleRandom = 0.5f;
            _burstParticles.Color = ParticleColor;
            _burstParticles.ColorRamp = new Gradient();
            var ramp = _burstParticles.ColorRamp;
            ramp.SetOffsets(new float[] { 0.0f, 0.5f, 1.0f });
            ramp.SetColors(new Color[] { ParticleColor, TrailColor, new Color(0, 0, 0, 0) });

            AddChild(_burstParticles);
        }

        private void SetupCoreLight()
        {
            _coreLight = new OmniLight3D();
            _coreLight.LightColor = BaseColor;
            _coreLight.LightEnergy = 2.0f * Intensity;
            _coreLight.OmniRange = 5.0f;
            _coreLight.OmniAttenuation = 1.0f;
            _coreLight.ShadowEnabled = false;

            AddChild(_coreLight);
        }

        public override void _Process(double delta)
        {
            _pulseTime += (float)delta * PulseSpeed;
            float pulse = Math.Abs(MathF.Sin(_pulseTime * 2.0f * MathF.PI / 1.5f));
            
            if (_coreMesh?.MaterialOverride is ShaderMaterial coreMat)
            {
                coreMat.SetShaderParameter("time", _pulseTime);
                coreMat.SetShaderParameter("intensity", Intensity * (1.0f + pulse * 0.3f));
            }

            if (_orbitParticles?.ProcessMaterial is ShaderMaterial particleMat)
            {
                particleMat.SetShaderParameter("time", _pulseTime);
            }

            if (_coreLight != null)
            {
                _coreLight.LightEnergy = 2.0f * Intensity * (1.0f + pulse * 0.5f);
            }

            _burstTimer += (float)delta;
            if (_burstTimer >= 3.0f + _rng.RandfRange(0f, 2f))
            {
                TriggerBurst();
                _burstTimer = 0f;
            }
        }

        public void TriggerBurst()
        {
            if (_burstParticles != null)
            {
                _burstParticles.Emitting = true;
                _burstParticles.Restart();
            }
        }

        public void SetThemeColors(Color baseColor, Color glowColor, Color pulseColor)
        {
            BaseColor = baseColor;
            GlowColor = glowColor;
            PulseColor = pulseColor;
            ParticleColor = baseColor;
            TrailColor = pulseColor;

            if (_coreMesh?.MaterialOverride is ShaderMaterial coreMat)
            {
                coreMat.SetShaderParameter("base_color", baseColor);
                coreMat.SetShaderParameter("glow_color", glowColor);
                coreMat.SetShaderParameter("pulse_color", pulseColor);
            }

            if (_orbitParticles?.ProcessMaterial is ShaderMaterial particleMat)
            {
                particleMat.SetShaderParameter("particle_color", baseColor);
                particleMat.SetShaderParameter("trail_color", pulseColor);
            }

            if (_coreLight != null)
            {
                _coreLight.LightColor = baseColor;
            }
        }

        public void SetParticleCount(int count)
        {
            ParticleCount = Math.Clamp(count, 4, 32);
            if (_orbitParticles != null)
                _orbitParticles.Amount = ParticleCount;
            
            if (_coreMesh?.MaterialOverride is ShaderMaterial coreMat)
                coreMat.SetShaderParameter("particle_count", ParticleCount);
        }

        public void SetIntensity(float intensity)
        {
            Intensity = Math.Clamp(intensity, 0.1f, 3.0f);
            if (_coreMesh?.MaterialOverride is ShaderMaterial coreMat)
                coreMat.SetShaderParameter("intensity", Intensity);
        }
    }
}