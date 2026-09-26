extends Node
class_name VoiceEngine

signal listening_started()
signal listening_stopped()
signal transcription_ready(text: String)
signal speaking_started()
signal speaking_finished()

@onready var audio_player := AudioStreamPlayer.new()
var _is_listening := false
var _is_speaking := false
var _piper_script := "res://scripts/audio/piper_tts.py"


func _ready() -> void:
	add_child(audio_player)


func start_listening() -> void:
	if _is_listening or _is_speaking:
		return
	_is_listening = true
	listening_started.emit()
	# TODO: iniciar captura de audio y enviar a backend /api/audio.


func stop_listening() -> void:
	if not _is_listening:
		return
	_is_listening = false
	listening_stopped.emit()
	# TODO: detener captura y procesar transcripción.


func speak(text: String) -> void:
	if _is_speaking or not text.strip_edges():
		return
	_is_speaking = true
	speaking_started.emit()

	var wav_path := _synthesize_local(text)
	if wav_path and FileAccess.file_exists(wav_path):
		var file := FileAccess.open(wav_path, FileAccess.READ)
		if file:
			var bytes := file.get_buffer(file.get_length())
			file.close()
			var wav := AudioStreamWAV.new()
			wav.data = bytes
			wav.format = AudioStreamWAV.FORMAT_WAV
			wav.mix_rate = 22050
			wav.stereo = false
			wav.loop_mode = AudioStreamWAV.LOOP_NONE
			wav.load_mode = AudioStreamWAV.LOAD_IMMEDIATE
			audio_player.stream = wav
			audio_player.play()
			audio_player.finished

	_is_speaking = false
	speaking_finished.emit()


func _synthesize_local(text: String) -> Variant:
	# Placeholder: en producción, invocar piper_tts.py como proceso externo.
	# Por ahora retornamos null para no bloquear.
	return null


func is_listening() -> bool:
	return _is_listening


func is_speaking() -> bool:
	return _is_speaking
