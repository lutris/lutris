pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

// The library's latest status and its cloud save transfers, floating over the games
Rectangle {
    id: toast

    required property QtObject controller

    // A running runtime update takes over the status until it's done
    readonly property string message: controller.runtimeUpdates.running ? controller.runtimeUpdates.statusText
                                                                        : controller.statusText
    readonly property bool shown: message.length > 0 || controller.cloudSaves.transfers.length > 0

    implicitWidth: Math.min(440, Math.max(240, rows.implicitWidth + 28))
    implicitHeight: rows.implicitHeight + 20
    radius: Theme.radiusLarge
    color: Theme.raised
    border.color: Theme.borderStrong
    visible: opacity > 0
    opacity: shown ? 1 : 0
    scale: shown ? 1 : 0.96

    Behavior on opacity { NumberAnimation { duration: 160 } }
    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

    ColumnLayout {
        id: rows
        anchors.fill: parent
        anchors.margins: 10
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 8

        Repeater {
            model: toast.controller.cloudSaves.transfers
            delegate: ColumnLayout {
                id: transfer

                required property var modelData

                Layout.fillWidth: true
                spacing: 6

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Icon {
                        symbol: "cloud"
                        size: 16
                        color: Theme.accentText
                    }

                    Label {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: transfer.modelData.label
                        textFormat: Text.PlainText
                    }

                    ToolButton {
                        text: qsTr("Skip Cloud Sync")
                        enabled: transfer.modelData.canSkip
                        font.pointSize: Theme.smallSize
                        onClicked: toast.controller.cloudSaves.skip(transfer.modelData.id)
                    }
                }

                ProgressBar {
                    Layout.fillWidth: true
                    value: transfer.modelData.progress
                    indeterminate: value === 0 && transfer.modelData.canSkip
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: status.text.length > 0
            spacing: 10

            BusyIndicator {
                implicitWidth: 22
                implicitHeight: 22
                padding: 0
                visible: running
                running: toast.controller.runtimeUpdates.running || toast.controller.updatingArtwork
            }

            Label {
                id: status
                objectName: "libraryStatus"
                Layout.fillWidth: true
                text: toast.message
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                maximumLineCount: 3
                elide: Text.ElideRight
                Accessible.role: Accessible.StatusBar
            }
        }
    }
}
