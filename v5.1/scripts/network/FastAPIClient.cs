using Godot;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace ARIA.Network
{
    [GlobalClass]
    public partial class FastAPIClient : Node
    {
        private HttpClient _httpClient;
        private string _baseUrl = "http://localhost:8000";
        private bool _isConnected = false;

        [Signal]
        public delegate void ConnectionChangedEventHandler(bool connected);

        [Signal]
        public delegate void ChatResponseReceivedEventHandler(string response, double latency, string model);

        [Signal]
        public delegate void SkillsLoadedEventHandler(Godot.Collections.Array<Godot.Collections.Dictionary> skills);

        [Signal]
        public delegate void SystemStatusReceivedEventHandler(Godot.Collections.Dictionary status);

        public override void _Ready()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(30);
            CheckConnection();
        }

        public async void CheckConnection()
        {
            try
            {
                var response = await _httpClient.GetAsync($"{_baseUrl}/health");
                _isConnected = response.IsSuccessStatusCode;
                EmitSignal(SignalName.ConnectionChanged, _isConnected);
            }
            catch
            {
                _isConnected = false;
                EmitSignal(SignalName.ConnectionChanged, false);
            }
        }

        public async Task<Godot.Collections.Dictionary> SendChatAsync(string message, string model = "dolphin-2.6-phi-2")
        {
            var request = new { message, model };
            var json = JsonSerializer.Serialize(request);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            try
            {
                var response = await _httpClient.PostAsync($"{_baseUrl}/api/chat", content);
                var responseJson = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<Godot.Collections.Dictionary>(responseJson);

                if (result != null && result.ContainsKey("response"))
                {
                    double latency = result.ContainsKey("latency") ? Convert.ToDouble(result["latency"]) : 0;
                    string modelUsed = result.ContainsKey("model") ? result["model"].ToString() : model;
                    EmitSignal(SignalName.ChatResponseReceived, result["response"].ToString(), latency, modelUsed);
                }

                return result ?? new Godot.Collections.Dictionary();
            }
            catch (Exception e)
            {
                GD.PrintErr($"Chat request failed: {e.Message}");
                return new Godot.Collections.Dictionary { ["error"] = e.Message };
            }
        }

        public async Task LoadSkillsAsync()
        {
            try
            {
                var response = await _httpClient.GetAsync($"{_baseUrl}/api/skills");
                var json = await response.Content.ReadAsStringAsync();
                var skills = JsonSerializer.Deserialize<Godot.Collections.Array<Godot.Collections.Dictionary>>(json);
                EmitSignal(SignalName.SkillsLoaded, skills ?? new Godot.Collections.Array<Godot.Collections.Dictionary>());
            }
            catch (Exception e)
            {
                GD.PrintErr($"Skills load failed: {e.Message}");
                EmitSignal(SignalName.SkillsLoaded, new Godot.Collections.Array<Godot.Collections.Dictionary>());
            }
        }

        public async Task LoadSystemStatusAsync()
        {
            try
            {
                var response = await _httpClient.GetAsync($"{_baseUrl}/api/system/status");
                var json = await response.Content.ReadAsStringAsync();
                var status = JsonSerializer.Deserialize<Godot.Collections.Dictionary>(json);
                EmitSignal(SignalName.SystemStatusReceived, status ?? new Godot.Collections.Dictionary());
            }
            catch (Exception e)
            {
                GD.PrintErr($"System status load failed: {e.Message}");
                EmitSignal(SignalName.SystemStatusReceived, new Godot.Collections.Dictionary());
            }
        }

        public bool IsConnected => _isConnected;
        public string BaseUrl => _baseUrl;

        public void SetBaseUrl(string url) => _baseUrl = url;
    }
}