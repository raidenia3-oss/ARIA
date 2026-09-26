using Godot;
using System;

namespace ARIA.UI
{
    public partial class Header : HBoxContainer
    {
        private Label _statusLabel;
        private Panel _statusDot;
        private OptionButton _themePicker;
        private TextureButton _btnMinimize;
        private TextureButton _btnMaximize;
        private TextureButton _btnClose;
        private SettingsManager _settings;
        private FastAPIClient _apiClient;

        public override void _Ready()
        {
            _statusLabel = GetNode<Label>("StatusLabel");
            _statusDot = GetNode<Panel>("StatusDot");
            _themePicker = GetNode<OptionButton>("ThemePicker");
            _btnMinimize = GetNode<TextureButton>("WindowControls/BtnMinimize");
            _btnMaximize = GetNode<TextureButton>("WindowControls/BtnMaximize");
            _btnClose = GetNode<TextureButton>("WindowControls/BtnClose");

            _settings = GetNode<SettingsManager>("/root/SettingsManager");
            _apiClient = GetNode<FastAPIClient>("/root/FastAPIClient");

            _themePicker.Selected = _settings.Get<int>("theme_index", 0);
            _themePicker.ItemSelected += OnThemeChanged;

            _btnMinimize.Pressed += () => OS.WindowMinimize();
            _btnMaximize.Pressed += () => OS.WindowMaximize();
            _btnClose.Pressed += () => GetTree().Quit();

            _apiClient.ConnectionChanged += OnConnectionChanged;
            UpdateConnectionStatus(_apiClient.IsConnected);
        }

        private void OnThemeChanged(long index)
        {
            string[] themes = { "cyan", "purple", "green", "orange" };
            if (index >= 0 && index < themes.Length)
            {
                _settings.Set("theme", themes[index]);
                _settings.Set("theme_index", (int)index);
                ApplyTheme(themes[index]);
                
                var eventBus = GetNode<EventBus>("/root/EventBus");
                eventBus?.Emit("theme_changed", new Godot.Collections.Dictionary { ["theme"] = themes[index] });
            }
        }

        private void OnConnectionChanged(bool connected)
        {
            UpdateConnectionStatus(connected);
        }

        private void UpdateConnectionStatus(bool connected)
        {
            if (connected)
            {
                _statusLabel.Text = "Conectado";
                _statusLabel.AddThemeColorOverride("font_color", new Color(0, 1, 0.5f, 1));
                _statusDot.AddThemeColorOverride("bg_color", new Color(0, 1, 0.5f, 1));
            }
            else
            {
                _statusLabel.Text = "Desconectado";
                _statusLabel.AddThemeColorOverride("font_color", new Color(1, 0.3f, 0.3f, 1));
                _statusDot.AddThemeColorOverride("bg_color", new Color(1, 0.3f, 0.3f, 1));
            }
        }

        private void ApplyTheme(string theme)
        {
            Color baseColor, glowColor, pulseColor;
            switch (theme)
            {
                case "purple":
                    baseColor = new Color(0.69f, 0.40f, 1.0f);
                    glowColor = new Color(0.85f, 0.60f, 1.0f);
                    pulseColor = new Color(0.22f, 0.74f, 0.98f);
                    break;
                case "green":
                    baseColor = new Color(0.20f, 0.85f, 0.45f);
                    glowColor = new Color(0.40f, 1.0f, 0.60f);
                    pulseColor = new Color(0.69f, 0.40f, 1.0f);
                    break;
                case "orange":
                    baseColor = new Color(1.0f, 0.65f, 0.15f);
                    glowColor = new Color(1.0f, 0.80f, 0.30f);
                    pulseColor = new Color(0.69f, 0.40f, 1.0f);
                    break;
                default: // cyan
                    baseColor = new Color(0.22f, 0.74f, 0.98f);
                    glowColor = new Color(0.0f, 0.83f, 1.0f);
                    pulseColor = new Color(0.69f, 0.40f, 1.0f);
                    break;
            }

            var orb = GetNode<OrbVisual3D>("/root/UI/OrbViewport/SubViewport/OrbVisual3D");
            orb?.SetThemeColors(baseColor, glowColor, pulseColor);
        }
    }
}