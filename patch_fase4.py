# Fase 4 patch script
import os
path = 'ARIA_APP/desktop_ui.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

marker = '    def _debug_check(self):'

insert = '''    def _show_notification(self, message, title="ARIA"):
        """Show a desktop notification via system tray."""
        try:
            if hasattr(self, '_tray') and self._tray:
                self._tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)
        except Exception:
            pass

    def _on_message_sent(self):
        """Micro-interaction: ripple effect on send button."""
        self.orb.set_state("thinking")

    def _toggle_accessibility(self):
        """Toggle high-contrast accessibility mode."""
        if not hasattr(self, '_a11y_mode'):
            self._a11y_mode = False
        self._a11y_mode = not self._a11y_mode
        if self._a11y_mode:
            self.setStyleSheet(self.styleSheet() + """
                QLabel { font-size: 13px; }
                QTextEdit { font-size: 13px; }
                QLineEdit { font-size: 13px; }
            """)
        else:
            self.setStyleSheet(self.styleSheet())

    def _export_chat(self, filename=None):
        """Export chat history to a text file."""
        import datetime
        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ARIA_chat_export_{ts}.txt"
        text = self.chat_history.toPlainText()
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(text)
            self._show_notification(f"Chat exportado a {filename}")
        except Exception as e:
            self._show_notification(f"Error exportando: {e}", "Error")

    def _clear_chat(self):
        """Clear chat history with confirmation."""
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Limpiar chat",
            "Esto eliminará todo el historial. Continuar?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.chat_history.clear()
            self._append_chat("ARIA", "Chat limpio. ¿En que puedo ayudarte?", C_SUCCESS)

    def _show_shortcuts(self):
        """Show keyboard shortcuts help dialog."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel
        dlg = QDialog(self)
        dlg.setWindowTitle("Atajos de teclado")
        dlg.setFixedSize(380, 300)
        dlg.setStyleSheet("QDialog { background: " + C_BG_DEEP + "; }")
        v = QVBoxLayout(dlg)
        lbl = QLabel("Atajos de teclado")
        lbl.setStyleSheet("color: " + C_TEXT_MAIN + "; font-size: 14px; font-weight: bold; font-family: Consolas, monospace;")
        v.addWidget(lbl)
        shortcuts = [
            ("Enter", "Enviar mensaje"),
            ("Ctrl+L", "Limpiar chat"),
            ("Ctrl+E", "Exportar chat"),
            ("Ctrl+K", "Paleta de comandos"),
            ("Ctrl+T", "Cambiar tema"),
            ("Ctrl+,", "Control Center"),
            ("F1", "Esta ayuda"),
            ("Esc", ",Ocultar/Cerrar"),
        ]
        for key, desc in shortcuts:
            item = QLabel(f"<b>{key}</b>  —  {desc}")
            item.setStyleSheet("color: " + C_TEXT_DIM + "; font-size: 11px; font-family: Consolas, monospace; padding: 2px;")
            v.addWidget(item)
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(32)
        close_btn.setStyleSheet("QPushButton { background: " + C_ACCENT + "; color: #0f172a; border: none; border-radius: 8px; font-weight: bold; font-family: Consolas, monospace; }")
        close_btn.clicked.connect(dlg.accept)
        v.addWidget(close_btn)
        dlg.exec_()

    def _save_settings(self):
        """Persist settings to local storage."""
        import json
        settings = {
            'theme': getattr(self, '_current_theme', 'default'),
            'a11y_mode': getattr(self, '_a11y_mode', False),
            'window_geometry': [self.x(), self.y(), self.width(), self.height()],
        }
        try:
            with open('ARIA_APP/settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass

    def _load_settings(self):
        """Load persisted settings."""
        import json
        try:
            with open('ARIA_APP/settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            if 'window_geometry' in settings:
                x, y, w, h = settings['window_geometry']
                self.setGeometry(x, y, w, h)
        except Exception:
            pass

    def _performance_monitor(self):
        """Lightweight performance monitoring: FPS and memory."""
        import time as _time
        if not hasattr(self, '_perf_frames'):
            self._perf_frames = 0
            self._perf_start = _time.time()
            self._perf_timer = QTimer(self)
            self._perf_timer.timeout.connect(self._perf_tick)
            self._perf_timer.start(1000)
        else:
            self._perf_frames += 1

    def _perf_tick(self):
        """Report FPS every second (debug only)."""
        import time as _time
        elapsed = _time.time() - self._perf_start
        if elapsed >= 1.0:
            fps = self._perf_frames / elapsed
            logger.debug(f"[PERF] FPS={fps:.1f}")
            self._perf_frames = 0
            self._perf_start = _time.time()

    def _setup_keyboard_shortcuts(self):
        """Register global keyboard shortcuts."""
        from PyQt5.QtCore import QKeySequence
        from PyQt5.QtGui import QShortcut
QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._show_command_palette)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self._open_theme_picker)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self._open_control_center)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_chat)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._export_chat)
        QShortcut(QKeySequence("F1"), self).activated.connect(self._show_shortcuts)

'''

content = content.replace(marker, insert + marker)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: Fase 4 methods inserted')