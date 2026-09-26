# -*- coding: utf-8 -*-
"""Insert Fase 3 methods into desktop_ui.py"""
path = 'ARIA_APP/desktop_ui.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

marker = '    def _debug_check(self):'

insert = '''    def _open_theme_picker(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle('Selector de tema')
        dlg.setFixedSize(320, 200)
        dlg.setStyleSheet('QDialog { background: ' + C_BG_DEEP + '; }')
        v = QVBoxLayout(dlg)
        lbl = QLabel('Elige un tema Serpentium')
        lbl.setStyleSheet('color: ' + C_TEXT_MAIN + '; font-size: 13px; font-family: Consolas, monospace;')
        v.addWidget(lbl)
        themes = [
            ('Cyan (default)', C_ACCENT, 'default'),
            ('Purple', C_SECONDARY, 'purple'),
            ('Green', C_SUCCESS, 'green'),
            ('Orange', C_WARNING, 'orange'),
        ]
        grid = QGridLayout()
        for i, (name, color, key) in enumerate(themes):
            btn = QPushButton(name)
            btn.setFixedHeight(36)
            btn.setStyleSheet('QPushButton { background: ' + color + '; color: #0f172a; border: none; border-radius: 8px; font-weight: bold; font-size: 11px; font-family: Consolas, monospace; }')
            btn.clicked.connect(lambda k=key: (self._apply_theme(k), dlg.accept()))
            grid.addWidget(btn, i // 2, i % 2)
        v.addLayout(grid)
        dlg.exec_()

    def _apply_theme(self, theme_key):
        themes = {
            'default': C_ACCENT,
            'purple': C_SECONDARY,
            'green': C_SUCCESS,
            'orange': C_WARNING,
        }
        color = themes.get(theme_key, C_ACCENT)
        self.orb._color = QColor(color)
        self.orb.update()
        self.status_label.setStyleSheet('color: ' + color + '; font-size: 11px;')
        self._append_chat('ARIA', 'Tema cambiado a ' + theme_key, color)

    def _open_control_center(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox
        dlg = QDialog(self)
        dlg.setWindowTitle('Control Center')
        dlg.setFixedSize(380, 280)
        dlg.setStyleSheet('QDialog { background: ' + C_BG_DEEP + '; }')
        v = QVBoxLayout(dlg)
        lbl = QLabel('Control Center')
        lbl.setStyleSheet('color: ' + C_TEXT_MAIN + '; font-size: 14px; font-weight: bold; font-family: Consolas, monospace;')
        v.addWidget(lbl)
        toggles = [
            ('Animaciones del orb', True),
            ('Transparencia (glass)', True),
            ('Streaming de texto', True),
            ('Notificaciones', True),
            ('Auto-inicio', False),
        ]
        for label_text, default in toggles:
            cb = QCheckBox(label_text)
            cb.setChecked(default)
            cb.setStyleSheet('QCheckBox { color: ' + C_TEXT_DIM + '; font-size: 11px; font-family: Consolas, monospace; }')
            v.addWidget(cb)
        close_btn = QPushButton('Guardar')
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet('QPushButton { background: ' + C_ACCENT + '; color: #0f172a; border: none; border-radius: 8px; font-weight: bold; font-family: Consolas, monospace; }')
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec_()

    def _show_command_palette(self):
        from PyQt5.QtWidgets import QDialog, QLineEdit, QVBoxLayout, QListWidget, QListWidgetItem
        dlg = QDialog(self)
        dlg.setWindowTitle('Comando')
        dlg.setFixedSize(400, 300)
        dlg.setStyleSheet('QDialog { background: ' + C_BG_DEEP + '; border: 1px solid ' + C_GLASS_BORDER + '; border-radius: 12px; }')
        v = QVBoxLayout(dlg)
        search = QLineEdit()
        search.setPlaceholderText(' Buscar comando o skill...')
        search.setStyleSheet('QLineEdit { background: rgba(15, 23, 42, 0.8); color: ' + C_TEXT_MAIN + '; border: 1px solid ' + C_GLASS_BORDER + '; border-radius: 8px; padding: 10px; font-family: Consolas, monospace; }')
        v.addWidget(search)
        list_w = QListWidget()
        list_w.setStyleSheet('QListWidget { background: transparent; border: none; } QListWidget::item::selected { background: rgba(56, 189, 248, 0.2); }')
        v.addWidget(list_w)
        commands = [
            ('Busqueda web', 'web.search'),
            ('Clima', 'weather'),
            ('Lista de archivos', 'files.list'),
            ('Abrir app', 'system.open'),
            ('Screenshot', 'system.screenshot'),
            ('Estado del sistema', 'system.status'),
            ('Configuracion', 'settings'),
        ]
        for name, cmd in commands:
            item = QListWidgetItem(name + '  [' + cmd + ']')
            item.setData(Qt.UserRole, cmd)
            list_w.addItem(item)
        def _filter(text):
            for i in range(list_w.count()):
                item = list_w.item(i)
                item.setHidden(text.lower() not in item.text().lower())
        search.textChanged.connect(_filter)
        def _select():
            items = list_w.selectedItems()
            if items:
                cmd = items[0].data(Qt.UserRole)
                self.msg_input.setText(cmd)
                dlg.accept()
        list_w.itemDoubleClicked.connect(_select)
        dlg.exec_()

'''

content = content.replace(marker, insert + marker)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: Fase 3 methods inserted')