using Godot;
using System;
using System.Collections.Generic;

namespace ARIA.UI
{
    [GlobalClass]
    public partial class SkillCircle : Control
    {
        private double _pollTimer = 0.0;
        private const double PollInterval = 5.0;

        private List<SkillData> _skills = new();
        private Vector2 _center = Vector2.Zero;
        private float _ringRadius = 50.0f;
        private float _ringThickness = 8.0f;

        private class SkillData
        {
            public string Name = "";
            public string Category = "";
            public int Level = 1;
            public int XP = 0;
            public int XPNeeded = 100;
            public bool Enabled = true;
        }

        private static readonly Dictionary<string, Color> CategoryColors = new()
        {
            { "system", new Color(0.22f, 0.74f, 0.98f) },   // cyan
            { "web", new Color(0.66f, 0.53f, 0.93f) },       // purple
            { "files", new Color(0.20f, 0.85f, 0.62f) },     // green
            { "research", new Color(0.96f, 0.37f, 0.07f) },  // orange
            { "brain", new Color(0.96f, 0.45f, 0.71f) },     // pink
            { "integration", new Color(0.38f, 0.65f, 0.98f) }, // blue
            { "improvement", new Color(0.98f, 0.74f, 0.14f) }, // yellow
        };

        public override void _Ready()
        {
            _center = new Vector2(Size.X / 2, Size.Y / 2);

            // Initialize with default skills
            _skills.Add(new SkillData { Name = "status", Category = "system", Level = 3, XP = 65, XPNeeded = 100 });
            _skills.Add(new SkillData { Name = "search", Category = "web", Level = 2, XP = 40, XPNeeded = 100 });
            _skills.Add(new SkillData { Name = "list", Category = "files", Level = 5, XP = 85, XPNeeded = 100 });
            _skills.Add(new SkillData { Name = "self-improvement", Category = "improvement", Level = 1, XP = 15, XPNeeded = 100 });

            QueueRedraw();
        }

        public override void _Process(double delta)
        {
            _pollTimer += delta;
            if (_pollTimer >= PollInterval)
            {
                _pollTimer = 0.0;
                PollSkillStatus();
            }
            QueueRedraw();
        }

        private void PollSkillStatus()
        {
            var rng = new RandomNumberGenerator();
            rng.Randomize();
            foreach (var skill in _skills)
            {
                // Small chance to gain XP
                if (rng.Randf() < 0.3f)
                {
                    skill.XP += rng.Randi(1, 5);
                    if (skill.XP >= skill.XPNeeded)
                    {
                        skill.Level++;
                        skill.XP = 0;
                        skill.XPNeeded = (int)(skill.XPNeeded * 1.5f);
                    }
                }
            }
        }

        public override void _Draw()
        {
            // Draw background circle
            DrawArc(_center, _ringRadius + _ringThickness + 10.0f, 0, 2 * Mathf.Pi,
                new Color(0.1f, 0.15f, 0.25f, 0.3f), 2.0f);

            // Draw each skill as a segment of the ring
            float anglePerSkill = 2 * Mathf.Pi / _skills.Count;
            for (int i = 0; i < _skills.Count; i++)
            {
                var skill = _skills[i];
                float startAngle = i * anglePerSkill - Mathf.Pi / 2;
                float endAngle = (i + 1) * anglePerSkill - Mathf.Pi / 2;

                // Background segment
                DrawArc(_center, _ringRadius, startAngle, endAngle,
                    new Color(0.15f, 0.20f, 0.30f, 0.8f), _ringThickness);

                // Progress segment
                float progress = (float)skill.XP / skill.XPNeeded;
                float progressEnd = startAngle + (endAngle - startAngle) * progress;
                Color catColor = CategoryColors.GetValueOrDefault(skill.Category, Colors.White);
                DrawArc(_center, _ringRadius, startAngle, progressEnd,
                    catColor, _ringThickness, 0.0f);

                // Level indicator dot
                Vector2 dotPos = _center + new Vector2(
                    Mathf.Cos(startAngle + anglePerSkill / 2),
                    Mathf.Sin(startAngle + anglePerSkill / 2)
                ) * _ringRadius;
                DrawCircle(dotPos, 3.0f, skill.Enabled ? catColor : new Color(0.3f, 0.3f, 0.3f));

                // Skill name label
                Vector2 labelPos = _center + new Vector2(
                    Mathf.Cos(startAngle + anglePerSkill / 2),
                    Mathf.Sin(startAngle + anglePerSkill / 2)
                ) * (_ringRadius + 18.0f);
                DrawString(GetFont(), labelPos, skill.Name, fontSize: 9, horizontalAlignment: HorizontalAlignment.Center);
            }

            // Center stats
            int totalSkills = _skills.Count;
            int totalLevel = 0;
            foreach (var s in _skills) totalLevel += s.Level;
            int avgLevel = totalSkills > 0 ? totalLevel / totalSkills : 0;

            DrawString(GetFont(), _center - new Vector2(20, 6), $"LVL {avgLevel}", fontSize: 18);
            DrawString(GetFont(), _center - new Vector2(22, 10), $"{totalSkills} skills", fontSize: 10);
            DrawString(GetFont(), _center - new Vector2(28, 22), $"XP {totalLevel * 25}", fontSize: 9);

            // Title
            DrawString(GetFont(), new Vector2(4, 16), "◇ Skill Progression", fontSize: 12);
        }
    }
}