pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "gameShortcutsDialog"

    required property QtObject controller
    required property string gameName

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(460, parent.width - 32)
    title: qsTr("Shortcuts for %1").arg(gameName)
    modal: true
    standardButtons: Dialog.Close

    contentItem: ColumnLayout {
        Label {
            visible: dialog.controller.busy && destinations.count === 0
            text: qsTr("Loading shortcuts…")
        }

        Label {
            visible: configuration.visible
            text: qsTr("Launch configuration")
        }

        ComboBox {
            id: configuration
            objectName: "shortcutConfigurationChoice"
            Layout.fillWidth: true
            visible: count > 1
            enabled: !dialog.controller.busy
            Accessible.name: qsTr("Launch configuration")
            model: dialog.controller.configurationLabels
        }

        Repeater {
            id: destinations
            model: dialog.controller.targets

            delegate: RowLayout {
                id: destination

                required property var modelData
                Layout.fillWidth: true

                Label {
                    Layout.fillWidth: true
                    text: destination.modelData.label
                    wrapMode: Text.WordWrap
                }

                Button {
                    objectName: destination.modelData.kind + "Shortcut"
                    text: destination.modelData.exists ? qsTr("Remove") : qsTr("Create")
                    Accessible.name: destination.modelData.exists ? qsTr("Remove %1 shortcut").arg(destination.modelData.label)
                                                            : qsTr("Create %1 shortcut").arg(destination.modelData.label)
                    enabled: !dialog.controller.busy
                    onClicked: dialog.controller.set_shortcut(destination.modelData.kind, !destination.modelData.exists,
                                                               configuration.currentIndex)
                }
            }
        }
    }
}
