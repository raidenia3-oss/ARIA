using Godot;
using System;
using System.Collections.Generic;

namespace ARIA.Core
{
    [GlobalClass]
    public partial class EventBus : Node
    {
        private static EventBus _instance;
        public static EventBus Instance => _instance;

        private Dictionary<string, List<Action<Godot.Collections.Dictionary>>> _eventHandlers = new();

        public override void _Ready()
        {
            if (_instance != null)
            {
                QueueFree();
                return;
            }
            _instance = this;
        }

        public void Emit(string eventName, Godot.Collections.Dictionary data = null)
        {
            if (_eventHandlers.TryGetValue(eventName, out var handlers))
            {
                foreach (var handler in handlers)
                {
                    try { handler(data ?? new Godot.Collections.Dictionary()); }
                    catch (Exception e) { GD.PrintErr($"Event handler error for {eventName}: {e.Message}"); }
                }
            }
        }

        public void Subscribe(string eventName, Action<Godot.Collections.Dictionary> handler)
        {
            if (!_eventHandlers.ContainsKey(eventName))
                _eventHandlers[eventName] = new List<Action<Godot.Collections.Dictionary>>();
            _eventHandlers[eventName].Add(handler);
        }

        public void Unsubscribe(string eventName, Action<Godot.Collections.Dictionary> handler)
        {
            if (_eventHandlers.TryGetValue(eventName, out var handlers))
                handlers.Remove(handler);
        }
    }
}