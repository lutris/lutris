pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

Dialog {
    id: dialog
    objectName: "localGameDialog"

    required property QtObject controller

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(500, parent.width - 32)
    title: controller.linking ? qsTr("Locate %1").arg(controller.gameName) : qsTr("Add a locally installed game")
    modal: true
    closePolicy: controller.working ? Popup.NoAutoClose : Popup.CloseOnEscape

    onOpened: (controller.linking ? executable : gameName).forceActiveFocus()

    Connections {
        target: dialog.controller
        function onRegistered(gameName: string) { dialog.close() }
    }

    NativeDialogs.FileDialog {
        id: picker
        title: qsTr("Choose a Linux executable")
        onAccepted: executable.text = dialog.controller.local_path(selectedFile)
    }

    contentItem: ColumnLayout {
        Label {
            Layout.fillWidth: true
            text: qsTr("Choose the executable for an existing Linux game. Lutris will not move or copy its files.")
            wrapMode: Text.WordWrap
        }

        Label {
            visible: gameName.visible
            text: qsTr("Name")
        }

        TextField {
            id: gameName
            objectName: "localGameName"
            Layout.fillWidth: true
            visible: !dialog.controller.linking
            enabled: !dialog.controller.working
            Accessible.name: qsTr("Name")
        }

        Label { text: qsTr("Executable") }

        RowLayout {
            Layout.fillWidth: true

            TextField {
                id: executable
                objectName: "localGameExecutable"
                Layout.fillWidth: true
                enabled: !dialog.controller.working
                Accessible.name: qsTr("Executable")
            }

            Button {
                text: qsTr("Browse…")
                icon.source: Theme.icon("folder")
                enabled: !dialog.controller.working
                Accessible.name: qsTr("Browse for executable")
                onClicked: picker.open()
            }
        }

        Label { text: qsTr("Arguments (optional)") }

        TextField {
            id: gameArguments
            objectName: "localGameArguments"
            Layout.fillWidth: true
            enabled: !dialog.controller.working
            Accessible.name: qsTr("Arguments (optional)")
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: dialog.controller.working
            indeterminate: visible
            Accessible.name: qsTr("Adding game…")
        }
    }

    footer: DialogButtonBox {
        Button {
            text: qsTr("Cancel")
            enabled: !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }

        Button {
            objectName: "confirmLocalGame"
            highlighted: true
            text: dialog.controller.linking ? qsTr("Link Game") : qsTr("Add Game")
            enabled: !dialog.controller.working && executable.text.trim().length > 0
                     && (dialog.controller.linking || gameName.text.trim().length > 0)
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.register(gameName.text, executable.text, gameArguments.text)
        }
    }
}
