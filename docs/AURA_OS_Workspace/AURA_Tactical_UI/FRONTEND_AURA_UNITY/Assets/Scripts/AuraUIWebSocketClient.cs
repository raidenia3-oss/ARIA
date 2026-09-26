using System;
using System.Collections.Concurrent;
using System.Threading;
using System.Threading.Tasks;
using NativeWebSocket;
using UnityEngine;
using UnityEngine.Events;

namespace AURA.UI
{
    /// <summary>
    /// Cliente WebSocket para AURA Backend en Unity (PC/Windows).
    /// Se conecta a ws://localhost:5000/ws y retransmite eventos al HUD 3D.
    /// </summary>
    public class AuraUIWebSocketClient : MonoBehaviour
    {
        [Header("Conexión Backend")]
        public string wsUrl = "ws://localhost:5000/ws";
        public float reconnectInterval = 2.0f;

        [Header("Eventos UI")]
        public UnityEvent<string> OnLogEvent;
        public UnityEvent<bool> OnConnectionChanged;
        public UnityEvent<NodeData[]> OnNodeUpdate;
        public UnityEvent<TaskData> OnTaskUpdate;
        public UnityEvent<TaskData> OnTaskAssigned;

        private WebSocket _ws;
        private CancellationTokenSource _cts;
        private ConcurrentQueue<Action> _mainThreadActions = new();
        private bool _isConnected;

        public bool IsConnected => _isConnected;

        void Update()
        {
            // Procesar acciones pendientes en el hilo principal de Unity
            while (_mainThreadActions.TryDequeue(out var action))
            {
                action?.Invoke();
            }
        }

        async void Start()
        {
            await ConnectAsync();
        }

        public async Task ConnectAsync()
        {
            _cts = new CancellationTokenSource();
            while (!_cts.IsCancellationRequested)
            {
                try
                {
                    if (_ws == null || _ws.State != WebSocketState.Open)
                    {
                        _ws = new WebSocket(wsUrl);
                        _ws.OnOpen += () =>
                        {
                            _isConnected = true;
                            _mainThreadActions.Enqueue(() => OnConnectionChanged?.Invoke(true));
                            Debug.Log("[AuraWS] Conectado al backend AURA");
                        };
                        _ws.OnMessage += (bytes) =>
                        {
                            var msg = System.Text.Encoding.UTF8.GetString(bytes);
                            ProcessMessage(msg);
                        };
                        _ws.OnError += (err) =>
                        {
                            _isConnected = false;
                            _mainThreadActions.Enqueue(() => OnConnectionChanged?.Invoke(false));
                            Debug.LogError($"[AuraWS] Error: {err}");
                        };
                        _ws.OnClose += (code) =>
                        {
                            _isConnected = false;
                            _mainThreadActions.Enqueue(() => OnConnectionChanged?.Invoke(false));
                            Debug.Log($"[AuraWS] Desconectado (code: {code})");
                        };

                        await _ws.Connect();
                    }

                    // Enviar heartbeat / suscripciones
                    if (_ws.State == WebSocketState.Open)
                    {
                        await _ws.SendText("{ \"action\": \"subscribe\", \"channel\": \"node_update\" }");
                        await _ws.SendText("{ \"action\": \"subscribe\", \"channel\": \"task_update\" }");
                        await _ws.SendText("{ \"action\": \"subscribe\", \"channel\": \"task_assigned\" }");
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[AuraWS] Reintentando en {reconnectInterval}s... ({ex.Message})");
                }

                await Task.Delay(TimeSpan.FromSeconds(reconnectInterval), _cts.Token);
            }
        }

        private void ProcessMessage(string json)
        {
            try
            {
                var data = JsonUtility.FromJson<WSMessage>(json);
                if (data == null) return;

                switch (data.event)
                {
                    case "node_update":
                        var nodes = JsonHelper.FromJson<NodeData[]>(JsonUtility.ToJson(data.data));
                        _mainThreadActions.Enqueue(() => OnNodeUpdate?.Invoke(nodes));
                        break;
                    case "task_update":
                        var task = JsonUtility.FromJson<TaskData>(JsonUtility.ToJson(data.data));
                        _mainThreadActions.Enqueue(() => OnTaskUpdate?.Invoke(task));
                        break;
                    case "task_assigned":
                        var assigned = JsonUtility.FromJson<TaskData>(JsonUtility.ToJson(data.data));
                        _mainThreadActions.Enqueue(() => OnTaskAssigned?.Invoke(assigned));
                        break;
                    default:
                        _mainThreadActions.Enqueue(() => OnLogEvent?.Invoke($"EVENT: {data.event}"));
                        break;
                }
            }
            catch (Exception ex)
            {
                Debug.LogError($"[AuraWS] Error parseando mensaje: {ex.Message}");
            }
        }

        /// <summary>
/// Asignar tarea a un nodo específico desde el cliente Unity.
        /// </summary>
        public async void AssignTask(string nodeId, string moduleType)
        {
            if (_ws == null || _ws.State != WebSocketState.Open) return;
            var payload = $"{{\"action\":\"assign_task\",\"nodeId\":\"{nodeId}\",\"module\":\"{moduleType}\"}}";
            await _ws.SendText(payload);
        }

        void OnApplicationQuit()
        {
            _cts?.Cancel();
            _ws?.Close();
        }

        [Serializable]
        private class WSMessage
        {
            public string @event;
            public object data;
        }
    }

    [Serializable]
    public class NodeData
    {
        public string id;
        public string name;
        public string type;
        public string status;
        public string location;
        public int battery;
        public int signal;
    }

    [Serializable]
    public class TaskData
    {
        public string id;
        public string nodeId;
        public string module;
        public string status;
        public int progress;
        public string[] output;
    }

    public static class JsonHelper
    {
        public static T[] FromJson<T>(string json)
        {
            var wrapper = JsonUtility.FromJson<Wrapper<T>>(json);
            return wrapper?.items ?? Array.Empty<T>();
        }

        [Serializable]
        private class Wrapper<T>
        {
            public T[] items;
        }
    }
}
