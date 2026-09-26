extends Node

signal chat_received(prompt: String, text: String, provider: String)
signal stream_token(token: String, done: bool)
signal gesture_detected(gesture: String, confidence: float, fingers: int)
signal wifi_update(networks: Array, zones: Array, motion: Array, anomalies: Array)
signal earthquake_risk_update(score: float, level: String, events: Array)
signal connection_lost()
signal connection_restored()
signal plugin_loaded(name: String)
signal plugin_unloaded(name: String)
