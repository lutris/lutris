pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "uninstallGameDialog"

    required property QtObject controller
    required property string gameName
    required property bool installed
    readonly property bool targetInstalled: controller.ready ? controller.installed : installed

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(500, parent.width - 32)
    title: targetInstalled ? qsTr("Uninstall %1").arg(gameName) : qsTr("Remove %1").arg(gameName)
    modal: true
    closePolicy: controller.working ? Popup.NoAutoClose : Popup.CloseOnEscape

    Connections {
        target: dialog.controller
        function onFinished() { dialog.close() }
    }

    contentItem: ColumnLayout {
        Label {
            Layout.fillWidth: true
            text: !dialog.controller.ready ? qsTr("Checking installation…")
                    : dialog.controller.installed ? qsTr("Lutris will remove this game's configuration and shortcuts.")
                    : qsTr("This game will no longer appear in your library.")
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }

        CheckBox {
            id: trashFiles
            objectName: "trashGameFiles"
            visible: dialog.controller.installed
            text: qsTr("Move the installation folder to the Trash")
            enabled: !dialog.controller.working && dialog.controller.filesUnavailableReason.length === 0
        }

        Label {
            Layout.fillWidth: true
            visible: trashFiles.visible && text.length > 0
            text: dialog.controller.filesUnavailableReason
                  || (trashFiles.checked ? qsTr("Everything under %1 will be moved to the Trash.").arg(dialog.controller.directory) : "")
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
        }

        CheckBox {
            id: removeEntry
            objectName: "removeGameEntry"
            visible: dialog.controller.installed
            enabled: !dialog.controller.working
            text: qsTr("Also remove this game from the library")
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: dialog.controller.working
            indeterminate: visible
            Accessible.name: dialog.targetInstalled ? qsTr("Uninstalling game…") : qsTr("Removing game…")
        }
    }

    footer: DialogButtonBox {
        Button {
            text: qsTr("Cancel")
            enabled: !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }

        Button {
            objectName: "confirmGameUninstall"
            highlighted: true
            text: dialog.targetInstalled ? qsTr("Uninstall") : qsTr("Remove")
            enabled: dialog.controller.ready && !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.DestructiveRole
            onClicked: dialog.controller.uninstall(trashFiles.checked, !dialog.controller.installed || removeEntry.checked)
        }
    }
}
