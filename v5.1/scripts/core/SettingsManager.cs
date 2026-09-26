using Godot;
using System;
using System.Collections.Generic;
using System.IO;

namespace ARIA.Core
{
    [GlobalClass]
    public partial class SettingsManager : Node
    {
        private string _settingsPath;
        private Godot.Collections.Dictionary _settings = new();

        public override void _Ready()
        {
            _settingsPath = Path.Combine(OS.GetUserDataDir(), "ARIA", "settings.json");
            LoadSettings();
        }

        private void LoadSettings()
        {
            try
            {
                if (File.Exists(_settingsPath))
                {
                    var json = File.ReadAllText(_settingsPath);
                    _settings = Json.ParseString(json).AsGodotDictionary();
                }
                else
                {
                    SetDefaults();
                }
            }
            catch
            {
                SetDefaults();
            }
        }

        private void SetDefaults()
        {
            _settings = new Godot.Collections.Dictionary
            {
                ["theme"] = "cyan",
                ["orb_intensity"] = 1.0,
                ["particle_count"] = 12,
                ["show_fps"] = false,
                ["auto_start_listening"] = false,
                ["voice_enabled"] = true,
                ["notifications_enabled"] = true,
                ["window_opacity"] = 1.0,
                ["language"] = "es"
            };
            SaveSettings();
        }

        public void SaveSettings()
        {
            try
            {
                var dir = Path.GetDirectoryName(_settingsPath);
                if (!Directory.Exists(dir))
                    Directory.CreateDirectory(dir);

                var json = Json.Stringify(_settings);
                File.WriteAllText(_settingsPath, json);
            }
            catch (Exception e)
            {
                GD.PrintErr($"Failed to save settings: {e.Message}");
            }
        }

        public T Get<T>(string key, T defaultValue = default)
        {
            if (_settings.TryGetValue(key, out var value))
            {
                try { return (T)Convert.ChangeType(value, typeof(T)); }
                catch { return defaultValue; }
            }
            return defaultValue;
        }

        public void Set(string key, object value)
        {
            _settings[key] = value;
            SaveSettings();
        }

        public Godot.Collections.Dictionary GetAll() => new(_settings);
    }
}