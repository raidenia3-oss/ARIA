// frontend/quickshell_widgets/AuraHUD.qml
// Panel glassmorphic para Quickshell / end4-pC (Hyprland)
// Lee ~/.local/share/quickshell/aura_telemetry.json y muestra CPU, RAM y Swarm.

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15
import Quickshell 1.0

Item {
    id: root
    width: 320
    height: 180
    visible: true

    // Tema AURA NUCLEUS OS
    readonly property color bgColor: Qt.rgba(0.02, 0.03, 0.06, 0.85)
    readonly property color borderColor: Qt.rgba(0.22, 0.74, 0.97, 0.35)
    readonly property color primaryColor: "#38bdf8"
    readonly property color successColor: "#22c55e"
    readonly property color warningColor: "#facc15"
    readonly property color dangerColor: "#ef4444"
    readonly property color textPrimary: "#e0e8ff"
    readonly property color textSecondary: "#94a3b8"

    property var telemetry: ({})

    Timer {
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            const path = StandardPaths.writableLocation(StandardPaths.HomePath) + "/.local/share/quickshell/aura_telemetry.json"
            try {
                const data = JSON.parse(File.read(path))
                root.telemetry = data
            } catch (e) {
                // Silencioso si el archivo aún no existe
                root.telemetry = {}
            }
        }
    }

    Rectangle {
        id: glassPanel
        anchors.fill: parent
        color: bgColor
        radius: 16
        border.color: borderColor
        border.width: 1

        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: Rectangle {
                width: glassPanel.width
                height: glassPanel.height
                radius: glassPanel.radius
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                width: 10
                height: 10
                radius: 5
                color: root.telemetry && root.telemetry.cpu !== undefined ? successColor : warningColor
            }

            Text {
                text: "AURA NUCLEUS"
                color: primaryColor
                font.pixelSize: 14
                font.weight: Font.Bold
                font.family: "JetBrains Mono, Fira Code, monospace"
            }

            Text {
                text: root.telemetry && root.telemetry.timestamp ? new Date(root.telemetry.timestamp * 1000).toLocaleTimeString() : "--:--:--"
                color: textSecondary
                font.pixelSize: 10
                Layout.alignment: Qt.AlignRight
                font.family: "JetBrains Mono, Fira Code, monospace"
            }
        }

        // Métricas principales
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: 12
            rowSpacing: 8

            // CPU
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "CPU"
                    color: textSecondary
                    font.pixelSize: 10
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }

                ProgressBar {
                    from: 0
                    to: 100
                    value: root.telemetry && root.telemetry.cpu ? root.telemetry.cpu : 0
                    Layout.fillWidth: true
                    background: Rectangle { color: Qt.rgba(0,0,0,0.3); radius: 4; height: 6 }
                    contentItem: Rectangle {
                        radius: 4
                        color: value > 80 ? dangerColor : value > 50 ? warningColor : primaryColor
                        height: 6
                        width: parent.width * parent.value / parent.to
                    }
                }

                Text {
                    text: (root.telemetry && root.telemetry.cpu ? root.telemetry.cpu.toFixed(1) : "0.0") + "%"
                    color: textPrimary
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }
            }

            // RAM
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "RAM"
                    color: textSecondary
                    font.pixelSize: 10
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }

                ProgressBar {
                    from: 0
                    to: 100
                    value: root.telemetry && root.telemetry.memory ? root.telemetry.memory.percent : 0
                    Layout.fillWidth: true
                    background: Rectangle { color: Qt.rgba(0,0,0,0.3); radius: 4; height: 6 }
                    contentItem: Rectangle {
                        radius: 4
                        color: value > 80 ? dangerColor : value > 50 ? warningColor : primaryColor
                        height: 6
                        width: parent.width * parent.value / parent.to
                    }
                }

                Text {
                    text: (root.telemetry && root.telemetry.memory ? root.telemetry.memory.percent.toFixed(1) : "0.0") + "%"
                    color: textPrimary
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }
            }

            // Swarm
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "SWARM"
                    color: textSecondary
                    font.pixelSize: 10
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }

                Text {
                    text: root.telemetry && root.telemetry.swarm ? (root.telemetry.swarm.active_agents + " / " + root.telemetry.swarm.active_tasks) : "0 / 0"
                    color: primaryColor
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }

                Text {
                    text: "HEALTH " + (root.telemetry && root.telemetry.swarm ? root.telemetry.swarm.health.toFixed(0) : "0") + "%"
                    color: textPrimary
                    font.pixelSize: 10
                    font.family: "JetBrains Mono, Fira Code, monospace"
                }
            }
        }

        // Indicadores de red
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: root.telemetry && root.telemetry.network ? successColor : dangerColor
            }

            Text {
                text: "NETWORK"
                color: textSecondary
                font.pixelSize: 10
                font.family: "JetBrains Mono, Fira Code, monospace"
            }

            Text {
                text: root.telemetry && root.telemetry.network ? "↑ " + (root.telemetry.network.bytes_sent / 1024 / 1024).toFixed(1) + " MB  ↓ " + (root.telemetry.network.bytes_recv / 1024 / 1024).toFixed(1) + " MB" : "Sin datos"
                color: textPrimary
                font.pixelSize: 10
                font.family: "JetBrains Mono, Fira Code, monospace"
            }
        }
    }
}
