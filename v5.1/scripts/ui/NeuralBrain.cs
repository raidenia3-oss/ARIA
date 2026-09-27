using Godot;
using System;
using System.Collections.Generic;

namespace ARIA.UI
{
    [GlobalClass]
    public partial class NeuralBrain : Control
    {
        private FastAPIClient _apiClient;
        private double _pollTimer = 0.0;
        private const double PollInterval = 3.0;

        // Agent colors (matching frontend NeuralBrain)
        private static readonly Dictionary<string, Color> AgentColors = new()
        {
            { "CodeAnalyzer", new Color(0.22f, 0.74f, 0.98f) },  // cyan
            { "DocsWriter", new Color(0.66f, 0.53f, 0.93f) },    // purple
            { "Tester", new Color(0.20f, 0.85f, 0.62f) },        // green
            { "ResearchAgent", new Color(0.96f, 0.37f, 0.07f) }, // orange
        };

        private List<AgentNode> _agents = new();
        private Vector2 _center = Vector2.Zero;
        private float _radius = 120.0f;

        private class AgentNode
        {
            public string Name = "";
            public string Status = "idle";
            public Color Color = Colors.White;
            public Vector2 Position = Vector2.Zero;
            public float Pulse = 0.0f;
            public float Angle = 0.0f;
        }

        public override void _Ready()
        {
            _apiClient = GetNode<FastAPIClient>("/root/FastAPIClient");
            _center = new Vector2(Size.X / 2, Size.Y / 2);

            // Initialize 4 agent nodes
            for (int i = 0; i < AgentColors.Count; i++)
            {
                var kvp = new List<Dictionary<string, Color>>(AgentColors)[i];
                var agent = new AgentNode
                {
                    Name = kvp.Key,
                    Color = kvp.Value,
                    Angle = i * (2.0f * Mathf.Pi / 4.0f),
                    Position = _center + new Vector2(
                        Mathf.Cos(i * (2.0f * Mathf.Pi / 4.0f)),
                        Mathf.Sin(i * (2.0f * Mathf.Pi / 4.0f))
                    ) * _radius
                };
                _agents.Add(agent);
            }

            _apiClient.ConnectionChanged += OnConnectionChanged;
            QueueRedraw();
        }

        public override void _Process(double delta)
        {
            _pollTimer += delta;

            // Update agent positions (orbiting)
            for (int i = 0; i < _agents.Count; i++)
            {
                var agent = _agents[i];
                agent.Angle += (float)delta * 0.5f;
                agent.Position = _center + new Vector2(
                    Mathf.Cos(agent.Angle),
                    Mathf.Sin(agent.Angle)
                ) * _radius;

                // Pulse effect for working agents
                if (agent.Status == "working")
                {
                    agent.Pulse += (float)delta * 8.0f;
                    if (agent.Pulse > 1.0f) agent.Pulse = 0.0f;
                }
            }

            if (_pollTimer >= PollInterval)
            {
                _pollTimer = 0.0;
                PollAgentStatus();
            }

            QueueRedraw();
        }

        private void PollAgentStatus()
        {
            // Simulate agent status polling
            var rng = new RandomNumberGenerator();
            rng.Randomize();
            foreach (var agent in _agents)
            {
                var roll = rng.Randf();
                if (roll < 0.6f)
                    agent.Status = "idle";
                else if (roll < 0.85f)
                    agent.Status = "working";
                else
                    agent.Status = "error";
            }
        }

        private void OnConnectionChanged(bool connected)
        {
            if (!connected)
            {
                foreach (var agent in _agents)
                    agent.Status = "error";
            }
            QueueRedraw();
        }

        public override void _Draw()
        {
            // Draw connections from center to each agent
            foreach (var agent in _agents)
            {
                DrawLine(_center, agent.Position, new Color(agent.Color.R, agent.Color.G, agent.Color.B, 0.3f), 1.5f);
            }

            // Draw center hub
            DrawCircle(_center, 8.0f, new Color(0.22f, 0.74f, 0.98f, 0.8f));
            DrawCircle(_center, 12.0f, new Color(0.22f, 0.74f, 0.98f, 0.2f));

            // Draw each agent node
            foreach (var agent in _agents)
            {
                float nodeRadius = 10.0f;
                if (agent.Status == "working")
                {
                    float pulseRadius = nodeRadius + agent.Pulse * 20.0f;
                    DrawCircle(agent.Position, pulseRadius, new Color(agent.Color.R, agent.Color.G, agent.Color.B, 0.3f - agent.Pulse * 0.3f));
                    nodeRadius = 14.0f;
                }
                else if (agent.Status == "error")
                {
                    nodeRadius = 12.0f;
                    DrawCircle(agent.Position, nodeRadius, new Color(0.96f, 0.20f, 0.20f, 0.8f));
                    DrawLine(agent.Position + new Vector2(-6, -6), agent.Position + new Vector2(6, 6), Colors.Red, 2.0f);
                    DrawLine(agent.Position + new Vector2(6, -6), agent.Position + new Vector2(-6, 6), Colors.Red, 2.0f);
                }
                else
                {
                    DrawCircle(agent.Position, nodeRadius, new Color(agent.Color.R, agent.Color.G, agent.Color.B, 0.8f));
                }

                // Outer glow
                DrawCircle(agent.Position, nodeRadius + 4.0f, new Color(agent.Color.R, agent.Color.G, agent.Color.B, 0.15f));

                // Label
                DrawString(GetFont(), agent.Position + new Vector2(12, 4), agent.Name, fontSize: 10);
            }

            // Title
            DrawString(GetFont(), new Vector2(4, 16), "◈ Neural Brain", fontSize: 12);
        }
    }
}