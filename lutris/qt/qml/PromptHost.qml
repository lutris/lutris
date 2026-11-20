pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Item {
    id: host

    required property QtObject prompts

    Dialog {
        id: notice
        objectName: "lutrisNotice"

        property string message: ""
        property string secondary: ""
        property bool rich: false

        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(500, parent.width - 32)
        modal: true
        standardButtons: Dialog.Ok
        onClosed: host.prompts.notice_finished()

        contentItem: ColumnLayout {
            Label {
                Layout.fillWidth: true
                text: notice.message
                textFormat: notice.rich ? Text.RichText : Text.PlainText
                wrapMode: Text.WordWrap
            }

            Label {
                Layout.fillWidth: true
                visible: notice.secondary.length > 0
                text: notice.secondary
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
            }
        }
    }

    Dialog {
        id: prompt
        objectName: "lutrisInput"

        property string message: ""
        property bool acceptsText: false

        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(500, parent.width - 32)
        modal: true
        standardButtons: acceptsText ? Dialog.Ok | Dialog.Cancel : Dialog.Yes | Dialog.No
        onAccepted: host.prompts.answer(true, acceptsText ? answerField.text : "")
        onRejected: host.prompts.answer(false, "")
        onOpened: if (acceptsText) answerField.forceActiveFocus()

        contentItem: ColumnLayout {
            Label {
                Layout.fillWidth: true
                text: prompt.message
                textFormat: Text.RichText
                wrapMode: Text.WordWrap
            }

            TextField {
                id: answerField
                Layout.fillWidth: true
                visible: prompt.acceptsText
                Accessible.name: prompt.title
                onAccepted: prompt.accept()
            }
        }
    }

    NativeDialogs.FileDialog {
        id: filePrompt
        onAccepted: host.prompts.answer_file(true, selectedFile)
        onRejected: host.prompts.answer_file(false, "")
    }

    Dialog {
        id: cloudConflict
        objectName: "cloudSaveConflict"
        property string description: ""

        title: qsTr("Cloud Save Conflict")
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(540, parent.width - 32)
        modal: true
        onRejected: host.prompts.answer(false, "")

        contentItem: ColumnLayout {
            Label {
                Layout.fillWidth: true
                text: cloudConflict.description
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Button {
                    text: qsTr("Keep Local Saves")
                    onClicked: {
                        host.prompts.answer(true, "upload")
                        cloudConflict.close()
                    }
                }
                Button {
                    text: qsTr("Keep Cloud Saves")
                    onClicked: {
                        host.prompts.answer(true, "download")
                        cloudConflict.close()
                    }
                }
                Button {
                    text: qsTr("Skip")
                    onClicked: cloudConflict.reject()
                }
            }
        }
    }

    Loader {
        id: configurationLoader
        active: false
        readonly property LaunchConfigurationDialog dialog: item as LaunchConfigurationDialog

        sourceComponent: LaunchConfigurationDialog {
            prompts: host.prompts
            onClosed: configurationLoader.active = false
        }
    }

    Connections {
        target: host.prompts

        function onNoticeRequested(title, message, secondary, rich) {
            notice.title = title
            notice.message = message
            notice.secondary = secondary
            notice.rich = rich
            notice.open()
        }

        function onInputRequested(kind, title, message, initial) {
            if (kind === "file") {
                filePrompt.title = title
                filePrompt.currentFolder = initial
                filePrompt.open()
                return
            }
            prompt.title = title
            prompt.message = message
            prompt.acceptsText = kind === "text"
            answerField.text = initial
            prompt.open()
        }

        function onConfigurationRequested(title, names, currentIndex, remembered) {
            configurationLoader.active = true
            if (configurationLoader.status === Loader.Ready) {
                const dialog = configurationLoader.dialog
                dialog.title = title
                dialog.configurationNames = names
                dialog.selectedIndex = currentIndex
                dialog.remembered = remembered
                dialog.open()
            }
        }

        function onConflictRequested(gameName, locationName) {
            cloudConflict.description = qsTr("Local and cloud saves for %1 (%2) both changed. Which copy should Lutris keep?")
                                         .arg(gameName).arg(locationName)
            cloudConflict.open()
        }

        function onCancelRequested() {
            if (configurationLoader.status === Loader.Ready)
                configurationLoader.dialog.reject()
            notice.close()
            prompt.reject()
            cloudConflict.reject()
            filePrompt.close()
        }
    }
}
