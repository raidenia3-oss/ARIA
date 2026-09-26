using Godot;
using System;
using System.Collections.Generic;
using System.Text.Json;

namespace ARIA.UI
{
    public partial class ChatPanel : VBoxContainer
    {
        private ScrollContainer _messagesScroll;
        private VBoxContainer _messagesContainer;
        private TextEdit _messageInput;
        private Button _sendButton;
        private Button _voiceButton;
        private Button _attachButton;
        private FastAPIClient _apiClient;
        private EventBus _eventBus;
        private bool _isStreaming = false;

        public override void _Ready()
        {
            _messagesScroll = GetNode<ScrollContainer>("MessagesScroll");
            _messagesContainer = GetNode<VBoxContainer>("MessagesScroll/MessagesContainer");
            _messageInput = GetNode<TextEdit>("InputArea/MessageInput");
            _sendButton = GetNode<Button>("InputArea/SendButton");
            _voiceButton = GetNode<Button>("InputArea/VoiceButton");
            _attachButton = GetNode<Button>("InputArea/AttachButton");

            _apiClient = GetNode<FastAPIClient>("/root/FastAPIClient");
            _eventBus = GetNode<EventBus>("/root/EventBus");

            _sendButton.Pressed += OnSendPressed;
            _messageInput.TextSubmitted += OnSendPressed;
            _voiceButton.Pressed += OnVoicePressed;
            _attachButton.Pressed += OnAttachPressed;

            _apiClient.ChatResponseReceived += OnChatResponse;
            _eventBus.Subscribe("theme_changed", OnThemeChanged);
        }

        private void OnSendPressed()
        {
            string message = _messageInput.Text.Trim();
            if (string.IsNullOrEmpty(message) || _isStreaming)
                return;

            AddMessage("user", message);
            _messageInput.Text = "";
            _isStreaming = true;
            _sendButton.Disabled = true;
            _sendButton.Text = "...";

            _apiClient.SendChatAsync(message);
        }

        private void OnChatResponse(string response, double latency, string model)
        {
            _isStreaming = false;
            _sendButton.Disabled = false;
            _sendButton.Text = "Enviar";

            AddMessage("assistant", response, latency, model);
        }

        private void OnVoicePressed()
        {
            _eventBus.Emit("voice_toggle", new Godot.Collections.Dictionary());
        }

        private void OnAttachPressed()
        {
            var dialog = new FileDialog();
            dialog.FileMode = FileDialog.FileModeEnum.OpenFiles;
            dialog.Filters = new string[] { "*.txt", "*.json", "*.md", "*.pdf", "*.png", "*.jpg" };
            dialog.FileSelected += (path) => 
            {
                AddMessage("system", $"Archivo adjunto: {path}");
            };
            AddChild(dialog);
            dialog.PopupCentered();
        }

        private void AddMessage(string role, string content, double latency = 0, string model = "")
        {
            var msgContainer = new HBoxContainer();
            msgContainer.CustomConstants.Separation = 8;

            var avatar = new Panel();
            avatar.CustomConstants.MinWidth = 36;
            avatar.CustomConstants.MinHeight = 36;
            var avatarStyle = new StyleBoxFlat();
            avatarStyle.CornerRadiusTopLeft = 18;
            avatarStyle.CornerRadiusTopRight = 18;
            avatarStyle.CornerRadiusBottomLeft = 18;
            avatarStyle.CornerRadiusBottomRight = 18;
            
            if (role == "user")
            {
                avatarStyle.BgColor = new Color(0.69f, 0.40f, 1.0f, 0.8f);
            }
            else if (role == "assistant")
            {
                avatarStyle.BgColor = new Color(0.22f, 0.74f, 0.98f, 0.8f);
            }
            else
            {
                avatarStyle.BgColor = new Color(0.5f, 0.5f, 0.5f, 0.5f);
            }
            avatar.AddThemeStyleboxOverride("panel", avatarStyle);

            var contentContainer = new VBoxContainer();
            contentContainer.HSizeFlags = Control.SizeFlags.ExpandFill;
            contentContainer.CustomConstants.Separation = 4;

            var roleLabel = new Label();
            roleLabel.Text = role == "user" ? "Tú" : (role == "assistant" ? "ARIA" : "Sistema");
            roleLabel.ThemeOverrideFontSizes.FontSize = 12;
            roleLabel.AddThemeColorOverride("font_color", role == "user" ? new Color(0.85f, 0.60f, 1.0f) : new Color(0.0f, 0.9f, 1.0f));

            var contentLabel = new RichTextLabel();
            contentLabel.Text = content;
            contentLabel.ThemeOverrideFontSizes.FontSize = 14;
            contentLabel.AddThemeColorOverride("font_color", new Color(0.9f, 0.9f, 0.95f));
            contentLabel.FitContent = true;
            contentLabel.ScrollActive = false;
            contentLabel.MouseFilter = Control.MouseFilterEnum.Ignore;

            if (role == "assistant" && latency > 0)
            {
                var metaLabel = new Label();
                metaLabel.Text = $"⚡ {latency:F1}s • {model}";
                metaLabel.ThemeOverrideFontSizes.FontSize = 11;
                metaLabel.AddThemeColorOverride("font_color", new Color(0.5f, 0.6f, 0.7f));
                contentContainer.AddChild(metaLabel);
            }

            contentContainer.AddChild(roleLabel);
            contentContainer.AddChild(contentLabel);

            msgContainer.AddChild(avatar);
            msgContainer.AddChild(contentContainer);

            _messagesContainer.AddChild(msgContainer);
            
            CallDeferred(nameof(ScrollToBottom));
        }

        private void ScrollToBottom()
        {
            _messagesScroll.GetVScrollBar().Value = _messagesScroll.GetVScrollBar().MaxValue;
        }

        private void OnThemeChanged(Godot.Collections.Dictionary data)
        {
            // Update message colors if needed
        }
    }
}