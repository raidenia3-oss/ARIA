extends Node
class_name PluginManager

signal plugin_loaded(name: String)
signal plugin_unloaded(name: String)

const PLUGINS_DIR := "res://plugins/"
var _loaded: Dictionary = {}


func _ready() -> void:
	_scan_plugins()


func _scan_plugins() -> void:
	if not DirAccess.dir_exists_absolute(PLUGINS_DIR):
		return
	var dir := DirAccess.open(PLUGINS_DIR)
	if not dir:
		return
	dir.list_dir_begin()
	var file := dir.get_next()
	while file != "":
		if dir.current_is_dir() and not file.begins_with("."):
			_try_load_plugin(file)
		file = dir.get_next()


func _try_load_plugin(name: String) -> void:
	var manifest_path := "%s%s/manifest.json" % [PLUGINS_DIR, name]
	if not FileAccess.file_exists(manifest_path):
		return
	var file := FileAccess.open(manifest_path, FileAccess.READ)
	if not file:
		return
	var text := file.get_as_text()
	file.close()
	var manifest = JSON.parse_string(text)
	if not manifest is Dictionary:
		return
	print("[PluginManager] Cargando plugin: %s v%s" % [manifest.get("name", name), manifest.get("version", "0.0.0")])
	_loaded[name] = manifest
	plugin_loaded.emit(name)


func unload_plugin(name: String) -> void:
	if _loaded.has(name):
		_loaded.erase(name)
		plugin_unloaded.emit(name)
		print("[PluginManager] Plugin descargado: %s" % name)


func get_loaded_plugins() -> Array:
	return _loaded.keys()
