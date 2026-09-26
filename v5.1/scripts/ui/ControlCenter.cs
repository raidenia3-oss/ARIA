using Godot;
using System;

namespace ARIA.UI
{
    public partial class ControlCenter : Panel
    {
        private SettingsManager _settings;
        private EventBus _eventBus;
        
        // Visual section
        private HSlider _orbIntensity;
        private Label _orbIntensityLabel;
        private SpinBox _particleCount;
        private Label _particleCountLabel;
        private CheckBox _showFPS;
        
        // Theme section
        private OptionButton _themePicker;
        
        // Notifications section
        private CheckBox _notificationsEnabled;
        private CheckBox _soundEnabled;
        
        // Voice section
        private CheckBox _voiceEnabled;
        private CheckBox _autoListen;
        
        // Window section
        private HSlider _windowOpacity;
        private Label _windowOpacityLabel;
        private CheckBox _alwaysOnTop;
        
        // Advanced section
        private Button _resetSettings;
        private Button _exportConfig;
        private Button _importConfig;

        public override void _Ready()
        {
            _settings = GetNode<SettingsManager>("/root/SettingsManager");
            _eventBus = GetNode<EventBus>("/root/EventBus");

            // Visual
            _orbIntensity = GetNode<HSlider>("ScrollContainer/Container/SectionVisual/OrbIntensity");
            _orbIntensityLabel = GetNode<Label>("ScrollContainer/Container/SectionVisual/OrbIntensityLabel");
            _particleCount = GetNode<SpinBox>("ScrollContainer/Container/SectionVisual/ParticleCount");
            _particleCountLabel = GetNode<Label>("ScrollContainer/Container/SectionVisual/ParticleCountLabel");
            _showFPS = GetNode<CheckBox>("ScrollContainer/Container/SectionVisual/ShowFPS");

            // Theme
            _themePicker = GetNode<OptionButton>("ScrollContainer/Container/SectionTheme/ThemePicker");

            // Notifications
            _notificationsEnabled = GetNode<CheckBox>("ScrollContainer/Container/SectionNotifications/NotificationsEnabled");
            _soundEnabled = GetNode<CheckBox>("ScrollContainer/Container/SectionNotifications/SoundEnabled");

            // Voice
            _voiceEnabled = GetNode<CheckBox>("ScrollContainer/Container/SectionVoice/VoiceEnabled");
            _autoListen = GetNode<CheckBox>("ScrollContainer/Container/SectionVoice/AutoListen");

            // Window
            _windowOpacity = GetNode<HSlider>("ScrollContainer/Container/SectionWindow/WindowOpacity");
            _windowOpacityLabel = GetNode<Label>("ScrollContainer/Container/SectionWindow/WindowOpacityLabel");
            _alwaysOnTop = GetNode<CheckBox>("ScrollContainer/Container/SectionWindow/AlwaysOnTop");

            // Advanced
            _resetSettings = GetNode<Button>("ScrollContainer/Container/SectionAdvanced/ResetSettings");
            _exportConfig = GetNode<Button>("ScrollContainer/Container/SectionAdvanced/ExportConfig");
            _importConfig = GetNode<Button>("ScrollContainer/Container/SectionAdvanced/ImportConfig");

            LoadSettings();
            ConnectSignals();
        }

        private void LoadSettings()
        {
            _orbIntensity.Value = _settings.Get<float>("orb_intensity", 1.0f);
            _orbIntensityLabel.Text = $"Intensidad Orb: {_orbIntensity.Value:F1}";
            
            _particleCount.Value = _settings.Get<int>("particle_count", 12);
            _particleCountLabel.Text = $"Partículas: {_particleCount.Value}";
            
            _showFPS.ButtonPressed = _settings.Get<bool>("show_fps", false);
            
            _themePicker.Selected = _settings.Get<int>("theme_index", 0);
            
            _notificationsEnabled.ButtonPressed = _settings.Get<bool>("notifications_enabled", true);
            _soundEnabled.ButtonPressed = _settings.Get<bool>("sound_enabled", false);
            
            _voiceEnabled.ButtonPressed = _settings.Get<bool>("voice_enabled", true);
            _autoListen.ButtonPressed = _settings.Get<bool>("auto_start_listening", false);
            
            _windowOpacity.Value = _settings.Get<float>("window_opacity", 1.0f);
            _windowOpacityLabel.Text = $"Opacidad: {(_windowOpacity.Value * 100):F0}%";
            
            _alwaysOnTop.ButtonPressed = _settings.Get<bool>("always_on_top", false);
        }

        private void ConnectSignals()
        {
            _orbIntensity.ValueChanged += OnOrbIntensityChanged;
            _particleCount.ValueChanged += OnParticleCountChanged;
            _showFPS.Toggled += OnShowFPSToggled;
            
            _themePicker.ItemSelected += OnThemeChanged;
            
            _notificationsEnabled.Toggled += OnNotificationsToggled;
            _soundEnabled.Toggled += OnSoundToggled;
            
            _voiceEnabled.Toggled += OnVoiceToggled;
            _autoListen.Toggled += OnAutoListenToggled;
            
            _windowOpacity.ValueChanged += OnWindowOpacityChanged;
            _alwaysOnTop.Toggled += OnAlwaysOnTopToggled;
            
            _resetSettings.Pressed += OnResetSettings;
            _exportConfig.Pressed += OnExportConfig;
            _importConfig.Pressed += OnImportConfig;
        }

        private void OnOrbIntensityChanged(double value)
        {
            float v = (float)value;
            _orbIntensityLabel.Text = $"Intensidad Orb: {v:F1}";
            _settings.Set("orb_intensity", v);
            
            var orb = GetNode<OrbVisual3D>("/root/UI/OrbViewport/SubViewport/OrbVisual3D");
            orb?.SetIntensity(v);
        }

        private void OnParticleCountChanged(double value)
        {
            int v = (int)value;
            _particleCountLabel.Text = $"Partículas: {v}";
            _settings.Set("particle_count", v);
            
            var orb = GetNode<OrbVisual3D>("/root/UI/OrbViewport/SubViewport/OrbVisual3D");
            orb?.SetParticleCount(v);
        }

        private void OnShowFPSToggled(bool pressed)
        {
            _settings.Set("show_fps", pressed);
            OS.SwapOkCancel = pressed; // Not ideal, but shows FPS in debug
            _eventBus.Emit("show_fps_changed", new Godot.Collections.Dictionary { ["enabled"] = pressed });
        }

        private void OnThemeChanged(long index)
        {
            string[] themes = { "cyan", "purple", "green", "orange" };
            if (index >= 0 && index < themes.Length)
            {
                _settings.Set("theme", themes[index]);
                _settings.Set("theme_index", (int)index);
                
                _eventBus.Emit("theme_changed", new Godot.Collections.Dictionary { ["theme"] = themes[index] });
            }
        }

        private void OnNotificationsToggled(bool pressed)
        {
            _settings.Set("notifications_enabled", pressed);
        }

        private void OnSoundToggled(bool pressed)
        {
            _settings.Set("sound_enabled", pressed);
        }

        private void OnVoiceToggled(bool pressed)
        {
            _settings.Set("voice_enabled", pressed);
            _eventBus.Emit("voice_enabled_changed", new Godot.Collections.Dictionary { ["enabled"] = pressed });
        }

        private void OnAutoListenToggled(bool pressed)
        {
            _settings.Set("auto_start_listening", pressed);
        }

        private void OnWindowOpacityChanged(double value)
        {
            float v = (float)value;
            _windowOpacityLabel.Text = $"Opacidad: {(v * 100):F0}%";
            _settings.Set("window_opacity", v);
            
            OS.WindowOpacity = v;
        }

        private void OnAlwaysOnTopToggled(bool pressed)
        {
            _settings.Set("always_on_top", pressed);
            OS.WindowAlwaysOnTop = pressed;
        }

        private void OnResetSettings()
        {
            var dialog = new ConfirmationDialog();
            dialog.Title = "Restablecer configuración";
            dialog.DialogText = "¿Seguro que quieres restablecer todos los ajustes a valores por defecto?";
            dialog.Confirmed += () =>
            {
                _settings.SetDefaults();
                LoadSettings();
                ApplyAllSettings();
            };
            AddChild(dialog);
            dialog.PopupCentered();
        }

        private void ApplyAllSettings()
        {
            var orb = GetNode<OrbVisual3D>("/root/UI/OrbViewport/SubViewport/OrbVisual3D");
            orb?.SetIntensity(_settings.Get<float>("orb_intensity", 1.0f));
            orb?.SetParticleCount(_settings.Get<int>("particle_count", 12));
            
            OS.WindowOpacity = _settings.Get<float>("window_opacity", 1.0f);
            OS.WindowAlwaysOnTop = _settings.Get<bool>("always_on_top", false);
            
            _eventBus.Emit("theme_changed", new Godot.Collections.Dictionary 
            { 
                ["theme"] = _settings.Get<string>("theme", "cyan") 
            });
        }

        private void OnExportConfig()
        {
            var dialog = new FileDialog();
            dialog.FileMode = FileDialog.FileModeEnum.SaveFile;
            dialog.Filters = new string[] { "*.json" };
            dialog.CurrentFile = "aria_config.json";
            dialog.FileSelected += (path) => 
            {
                var allSettings = _settings.GetAll();
                var json = Json.Stringify(allSettings);
                try
                {
                    using var file = FileAccess.Open(path, FileAccess.ModeFlags.Write);
                    file.StoreString(json);
                    GD.Print($"Config exported to {path}");
                }
                catch (Exception e)
                {
                    GD.PrintErr($"Export failed: {e.Message}");
                }
            };
            AddChild(dialog);
            dialog.PopupCentered();
        }

        private void OnImportConfig()
        {
            var dialog = new FileDialog();
            dialog.FileMode = FileDialog.FileModeEnum.OpenFile;
            dialog.Filters = new string[] { "*.json" };
            dialog.FileSelected += (path) => 
            {
                try
                {
                    using var file = FileAccess.Open(path, FileAccess.ModeFlags.Read);
                    var json = file.GetAsText();
                    var dict = Json.ParseString(json).AsGodotDictionary();
                    
                    foreach (var kvp in dict)
                    {
                        _settings.Set(kvp.Key.ToString(), kvp.Value);
                    }
                    
                    LoadSettings();
                    ApplyAllSettings();
                    GD.Print($"Config imported from {path}");
                }
                catch (Exception e)
                {
                    GD.PrintErr($"Import failed: {e.Message}");
                }
            };
            AddChild(dialog);
            dialog.PopupCentered();
        }
    }
}