import sys, os, time
sys.path.insert(0, 'AURA_APP')
os.environ['AURA_LOGIC_PROCESS'] = '1'
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import desktop_ui

app = QApplication(sys.argv)
app.setStyle('Fusion')
app.setQuitOnLastWindowClosed(False)

ipc = desktop_ui.IPCClient('AURA_APP/aria_logic_engine.py')
ipc.start()
window = desktop_ui.ChatWindow(ipc)
window.load_skills()
window.move(100, 100)
window.show()
window.raise_()
window.activateWindow()

print('Visible:', window.isVisible(), flush=True)
print('Geometry:', window.geometry().toString(), flush=True)
print('WinId:', hex(int(window.winId())), flush=True)

QTimer.singleShot(4000, app.quit)
sys.exit(app.exec_())