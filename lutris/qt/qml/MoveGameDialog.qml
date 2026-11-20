pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "moveGameDialog"

    required property QtObject controller
    required property string gameName

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(500, parent.width - 32)
    title: qsTr("Move %1").arg(gameName)
    modal: true
    closePolicy: controller.working ? Popup.NoAutoClose : Popup.CloseOnEscape

    Connections {
        target: dialog.controller
        function onFinished() { dialog.close() }
    }

    NativeDialogs.FolderDialog {
        id: picker
        title: qsTr("Choose Destination Folder")
        onAccepted: dialog.controller.choose_destination(selectedFolder)
    }

    contentItem: ColumnLayout {
        Label {
            Layout.fillWidth: true
            text: !dialog.controller.ready ? qsTr("Checking installation…")
                    : !dialog.controller.installed ? qsTr("This game is not installed.")
                    : dialog.controller.filesUnavailableReason || qsTr("Choose a folder to move this installation into.")
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }

        Label {
            Layout.fillWidth: true
            visible: dialog.controller.directory.length > 0
            text: qsTr("Current location: %1").arg(dialog.controller.directory)
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
        }

        Label {
            Layout.fillWidth: true
            visible: dialog.controller.moveTarget.length > 0
            text: qsTr("New location: %1").arg(dialog.controller.moveTarget)
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
        }

        Button {
            text: qsTr("Choose Folder…")
            enabled: dialog.controller.ready && dialog.controller.installed && !dialog.controller.working
                     && dialog.controller.filesUnavailableReason.length === 0
            onClicked: picker.open()
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: dialog.controller.working
            indeterminate: visible
            Accessible.name: qsTr("Moving game…")
        }
    }

    footer: DialogButtonBox {
        Button {
            text: qsTr("Cancel")
            enabled: !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }

        Button {
            objectName: "confirmGameMove"
            highlighted: true
            text: qsTr("Move")
            enabled: dialog.controller.moveTarget.length > 0 && !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.move()
        }
    }
}
