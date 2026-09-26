import os, re

class SceneBuilder:
    """
    Genera archivos .tscn válidos para Godot 4.x
    sin necesidad de abrir el editor.
    """

    def __init__(self, project_path="godot_game"):
        self.project_path = project_path
        self._res_counter = 1
        self._resources = []
        self._nodes = []

    def _reset(self):
        self._res_counter = 1
        self._resources = []
        self._nodes = []

    def _add_script(self, script_path):
        uid = self._res_counter
        self._res_counter += 1
        self._resources.append(
            f'[ext_resource type="Script" path="res://{script_path}" id="{uid}"]'
        )
        return uid

    def _node_line(self, name, type, parent=None, script_id=None):
        line = f'[node name="{name}" type="{type}"'
        if parent:
            line += f' parent="{parent}"'
        line += "]"
        if script_id:
            line += f'\nscript = ExtResource("{script_id}")'
        return line

    def build_scene(self, root_name, root_type, script_path=None,
                    children=None):
        """
        Construye un .tscn completo.
        children = [{"name": str, "type": str, "parent": str,
                     "script": str, "props": dict}]
        """
        self._reset()
        script_ids = {}

        # Registrar scripts
        if script_path:
            script_ids["root"] = self._add_script(script_path)
        if children:
            for c in children:
                if c.get("script"):
                    script_ids[c["name"]] = self._add_script(c["script"])

        load_steps = 1 + len(self._resources)
        header = f"[gd_scene load_steps={load_steps} format=3]\n"

        # Nodo raíz
        root_sid = script_ids.get("root")
        self._nodes.append(self._node_line(root_name, root_type,
                                           script_id=root_sid))

        # Hijos
        if children:
            for c in children:
                sid = script_ids.get(c["name"])
                self._nodes.append(self._node_line(
                    c["name"], c["type"],
                    parent=c.get("parent", "."),
                    script_id=sid
                ))
                # Propiedades extra
                if c.get("props"):
                    for k, v in c["props"].items():
                        self._nodes.append(f"{k} = {v}")

        content = header
        content += "\n".join(self._resources)
        if self._resources:
            content += "\n"
        content += "\n"
        content += "\n\n".join(self._nodes)
        content += "\n"
        return content

    def save(self, content, filename):
        path = os.path.join(self.project_path, "scenes", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print(f"✅ Escena guardada: {path}")
        return path

    # ── ESCENAS PREBUILT ──────────────────────────────────────

    def build_hud(self):
        content = self.build_scene(
            root_name="HUD", root_type="CanvasLayer",
            script_path="scripts/HUD.gd",
            children=[
                {"name": "VBox", "type": "VBoxContainer", "parent": "."},
                {"name": "XPBar", "type": "ProgressBar", "parent": "VBox",
                 "props": {"min_value": "0", "max_value": "100",
                           "value": "0"}},
                {"name": "LevelLabel", "type": "Label", "parent": "VBox",
                 "props": {"text": '"Nivel 1"'}},
                {"name": "GoldLabel", "type": "Label", "parent": "VBox",
                 "props": {"text": '"Gold: 0"'}},
                {"name": "EventLog", "type": "RichTextLabel",
                 "parent": "VBox",
                 "props": {"custom_minimum_size":
                           "Vector2(200, 100)"}},
                {"name": "ConnectionDot", "type": "ColorRect",
                 "parent": "VBox",
                 "props": {"color": "Color(1, 0, 0, 1)",
                           "custom_minimum_size": "Vector2(12, 12)"}},
            ]
        )
        return self.save(content, "HUD.tscn")

    def build_enemy(self):
        content = self.build_scene(
            root_name="Enemy", root_type="CharacterBody2D",
            script_path="scripts/Enemy.gd",
            children=[
                {"name": "Sprite2D", "type": "Sprite2D", "parent": "."},
                {"name": "HPBar", "type": "ProgressBar", "parent": ".",
                 "props": {"min_value": "0", "max_value": "100",
                           "value": "100"}},
                {"name": "NameLabel", "type": "Label", "parent": "."},
                {"name": "Col", "type": "CollisionShape2D", "parent": "."},
            ]
        )
        return self.save(content, "Enemy.tscn")

    def build_main_menu(self):
        content = self.build_scene(
            root_name="MainMenu", root_type="Control",
            script_path="scripts/MainMenu.gd",
            children=[
                {"name": "Center", "type": "CenterContainer",
                 "parent": "."},
                {"name": "VBox", "type": "VBoxContainer",
                 "parent": "Center"},
                {"name": "Title", "type": "Label", "parent": "Center/VBox",
                 "props": {"text": '"AURA/AME — Idle RPG"'}},
                {"name": "StatusDot", "type": "ColorRect",
                 "parent": "Center/VBox",
                 "props": {"color": "Color(1,0,0,1)",
                           "custom_minimum_size": "Vector2(12,12)"}},
                {"name": "StatusLabel", "type": "Label",
                 "parent": "Center/VBox",
                 "props": {"text": '"Desconectado"'}},
                {"name": "PlayBtn", "type": "Button",
                 "parent": "Center/VBox",
                 "props": {"text": '"JUGAR"'}},
                {"name": "SyncBtn", "type": "Button",
                 "parent": "Center/VBox",
                 "props": {"text": '"SINCRONIZAR CON AURA"'}},
            ]
        )
        return self.save(content, "MainMenu.tscn")

    def build_game_world(self):
        content = self.build_scene(
            root_name="GameWorld", root_type="Node2D",
            script_path="scripts/GameWorld.gd",
            children=[
                {"name": "Background", "type": "ColorRect", "parent": ".",
                 "props": {"color": "Color(0.05, 0.05, 0.1, 1)",
                           "size": "Vector2(1920, 1080)"}},
                {"name": "HUD", "type": "CanvasLayer", "parent": "."},
                {"name": "EnemySpawner", "type": "Node2D", "parent": "."},
                {"name": "IdleRPGCore", "type": "Node", "parent": "."},
            ]
        )
        return self.save(content, "GameWorld.tscn")

    def build_all(self):
        print("🏗️  Construyendo todas las escenas...")
        self.build_hud()
        self.build_enemy()
        self.build_main_menu()
        self.build_game_world()
        print("✅ Todas las escenas creadas")

if __name__ == "__main__":
    builder = SceneBuilder()
    builder.build_all()