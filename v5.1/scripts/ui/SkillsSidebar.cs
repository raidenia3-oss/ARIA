using Godot;
using System;
using System.Collections.Generic;
using System.Linq;

namespace ARIA.UI
{
    public partial class SkillsSidebar : VBoxContainer
    {
        private Label _skillCount;
        private LineEdit _searchBox;
        private HBoxContainer _categories;
        private VBoxContainer _skillsContainer;
        private FastAPIClient _apiClient;
        private EventBus _eventBus;
        private List<Godot.Collections.Dictionary> _allSkills = new();
        private string _currentCategory = "all";
        private string _searchText = "";

        public override void _Ready()
        {
            _skillCount = GetNode<Label>("Header/SkillCount");
            _searchBox = GetNode<LineEdit>("SearchBox");
            _categories = GetNode<HBoxContainer>("Categories");
            _skillsContainer = GetNode<VBoxContainer>("SkillsScroll/SkillsContainer");

            _apiClient = GetNode<FastAPIClient>("/root/FastAPIClient");
            _eventBus = GetNode<EventBus>("/root/EventBus");

            _searchBox.TextChanged += OnSearchChanged;
            
            foreach (Node child in _categories.GetChildren())
            {
                if (child is Button btn)
                {
                    btn.Pressed += () => OnCategorySelected(btn.Name.Replace("Cat", "").ToLower());
                }
            }

            _apiClient.SkillsLoaded += OnSkillsLoaded;
            _apiClient.LoadSkillsAsync();
        }

        private void OnSkillsLoaded(Godot.Collections.Array<Godot.Collections.Dictionary> skills)
        {
            _allSkills = skills.ToList();
            _skillCount.Text = _allSkills.Count.ToString();
            FilterAndRenderSkills();
        }

        private void OnSearchChanged(string text)
        {
            _searchText = text.ToLower();
            FilterAndRenderSkills();
        }

        private void OnCategorySelected(string category)
        {
            _currentCategory = category;
            UpdateCategoryButtons();
            FilterAndRenderSkills();
        }

        private void UpdateCategoryButtons()
        {
            foreach (Node child in _categories.GetChildren())
            {
                if (child is Button btn)
                {
                    string cat = btn.Name.Replace("Cat", "").ToLower();
                    if (cat == _currentCategory)
                    {
                        btn.AddThemeStyleboxOverride("normal", CreateStyleBox(new Color(0.22f, 0.74f, 0.98f, 0.3f), new Color(0.22f, 0.74f, 0.98f, 0.8f)));
                        btn.AddThemeColorOverride("font_color", new Color(1, 1, 1));
                    }
                    else
                    {
                        btn.AddThemeStyleboxOverride("normal", CreateStyleBox(new Color(0.1f, 0.15f, 0.25f, 0.8f), new Color(0.15f, 0.25f, 0.4f, 0.5f)));
                        btn.AddThemeColorOverride("font_color", new Color(0.7f, 0.8f, 0.9f));
                    }
                }
            }
        }

        private StyleBoxFlat CreateStyleBox(Color bg, Color border)
        {
            var style = new StyleBoxFlat();
            style.BgColor = bg;
            style.BorderColor = border;
            style.BorderWidth = 1;
            style.CornerRadiusTopLeft = 6;
            style.CornerRadiusTopRight = 6;
            style.CornerRadiusBottomLeft = 6;
            style.CornerRadiusBottomRight = 6;
            return style;
        }

        private void FilterAndRenderSkills()
        {
            foreach (Node child in _skillsContainer.GetChildren())
                child.QueueFree();

            var filtered = _allSkills.Where(s => 
            {
                bool catMatch = _currentCategory == "all" || s.GetValueOrDefault("category", "").ToString().ToLower() == _currentCategory;
                bool searchMatch = string.IsNullOrEmpty(_searchText) || 
                    s.GetValueOrDefault("name", "").ToString().ToLower().Contains(_searchText) ||
                    s.GetValueOrDefault("description", "").ToString().ToLower().Contains(_searchText);
                return catMatch && searchMatch;
            }).ToList();

            foreach (var skill in filtered)
            {
                CreateSkillCard(skill);
            }
        }

        private void CreateSkillCard(Godot.Collections.Dictionary skill)
        {
            var card = new Panel();
            card.CustomConstants.MinHeight = 80;
            card.AddThemeStyleboxOverride("panel", CreateSkillCardStyle());

            var mainContainer = new HBoxContainer();
            mainContainer.CustomConstants.Separation = 12;

            var iconPanel = new Panel();
            iconPanel.CustomConstants.MinWidth = 48;
            iconPanel.CustomConstants.MinHeight = 48;
            var iconStyle = new StyleBoxFlat();
            iconStyle.BgColor = new Color(0.22f, 0.74f, 0.98f, 0.15f);
            iconStyle.CornerRadiusTopLeft = 8;
            iconStyle.CornerRadiusTopRight = 8;
            iconStyle.CornerRadiusBottomLeft = 8;
            iconStyle.CornerRadiusBottomRight = 8;
            iconStyle.BorderWidth = 1;
            iconStyle.BorderColor = new Color(0.22f, 0.74f, 0.98f, 0.5f);
            iconPanel.AddThemeStyleboxOverride("panel", iconStyle);

            var iconLabel = new Label();
            iconLabel.Text = skill.GetValueOrDefault("icon", "⚡").ToString();
            iconLabel.HorizontalAlignment = HorizontalAlignment.Center;
            iconLabel.VerticalAlignment = VerticalAlignment.Center;
            iconLabel.ThemeOverrideFontSizes.FontSize = 24;
            iconPanel.AddChild(iconLabel);

            var infoContainer = new VBoxContainer();
            infoContainer.HSizeFlags = Control.SizeFlags.ExpandFill;
            infoContainer.CustomConstants.Separation = 4;

            var nameLabel = new Label();
            nameLabel.Text = skill.GetValueOrDefault("name", "Skill").ToString();
            nameLabel.ThemeOverrideFontSizes.FontSize = 13;
            nameLabel.AddThemeColorOverride("font_color", new Color(0.95f, 0.95f, 1f));

            var descLabel = new Label();
            descLabel.Text = skill.GetValueOrDefault("description", "").ToString();
            descLabel.ThemeOverrideFontSizes.FontSize = 11;
            descLabel.AddThemeColorOverride("font_color", new Color(0.6f, 0.7f, 0.8f));
            descLabel.AutowrapMode = TextServer.AutowrapMode.WordSmart;

            var metaContainer = new HBoxContainer();
            metaContainer.CustomConstants.Separation = 8;

            var categoryLabel = new Label();
            categoryLabel.Text = skill.GetValueOrDefault("category", "general").ToString().ToUpper();
            categoryLabel.ThemeOverrideFontSizes.FontSize = 10;
            categoryLabel.AddThemeColorOverride("font_color", new Color(0.69f, 0.40f, 1.0f));

            var enabledCheck = new CheckBox();
            enabledCheck.Text = "";
            enabledCheck.ButtonPressed = skill.GetValueOrDefault("enabled", true).AsBool();
            enabledCheck.Toggled += (pressed) => OnSkillToggled(skill, pressed);

            infoContainer.AddChild(nameLabel);
            infoContainer.AddChild(descLabel);
            metaContainer.AddChild(categoryLabel);
            metaContainer.AddChild(new Control() { HSizeFlags = Control.SizeFlags.ExpandFill });
            metaContainer.AddChild(enabledCheck);
            infoContainer.AddChild(metaContainer);

            mainContainer.AddChild(iconPanel);
            mainContainer.AddChild(infoContainer);
            card.AddChild(mainContainer);

            _skillsContainer.AddChild(card);
        }

        private StyleBoxFlat CreateSkillCardStyle()
        {
            var style = new StyleBoxFlat();
            style.BgColor = new Color(0.05f, 0.08f, 0.15f, 0.9f);
            style.BorderColor = new Color(0.15f, 0.25f, 0.4f, 0.3f);
            style.BorderWidth = 1;
            style.CornerRadiusTopLeft = 10;
            style.CornerRadiusTopRight = 10;
            style.CornerRadiusBottomLeft = 10;
            style.CornerRadiusBottomRight = 10;
            return style;
        }

        private void OnSkillToggled(Godot.Collections.Dictionary skill, bool enabled)
        {
            skill["enabled"] = enabled;
            _eventBus.Emit("skill_toggled", new Godot.Collections.Dictionary 
            { 
                ["skill_id"] = skill.GetValueOrDefault("id", "").ToString(),
                ["enabled"] = enabled
            });
        }
    }
}