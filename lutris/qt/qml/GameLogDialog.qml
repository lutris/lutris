import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs as NativeDialogs

Dialog {
    id: dialog
    objectName: "gameLogDialog"

    required property QtObject controller
    required property string gameName

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(900, parent.width - 32)
    height: Math.min(600, parent.height - 32)
    title: qsTr("Log for %1").arg(gameName)
    modal: true
    standardButtons: Dialog.Close
    onOpened: {
        log.text = controller.logText
        log.cursorPosition = log.length
    }

    contentItem: ColumnLayout {
        RowLayout {
            Layout.fillWidth: true

            TextField {
                id: search
                Layout.fillWidth: true
                placeholderText: qsTr("Find in log")
                Accessible.name: placeholderText
                onAccepted: findNext.clicked()
                onTextEdited: log.deselect()
            }

            Button {
                id: findNext
                text: qsTr("Find Next")
                enabled: search.text.length > 0
                onClicked: {
                    follow.checked = false
                    const needle = search.text.toLowerCase()
                    const haystack = log.text.toLowerCase()
                    let index = haystack.indexOf(needle, log.selectionEnd)
                    if (index === -1)
                        index = haystack.indexOf(needle)
                    if (index !== -1) {
                        log.cursorPosition = index + needle.length
                        log.select(index, index + needle.length)
                    }
                }
            }

            Button {
                text: qsTr("Save Log…")
                enabled: log.length > 0
                onClicked: saveDialog.open()
            }
        }

        CheckBox {
            id: follow
            text: qsTr("Follow Output")
            checked: true
            onToggled: if (checked) log.cursorPosition = log.length
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            TextArea {
                id: log
                objectName: "gameLogText"
                Accessible.name: qsTr("Game log")
                readOnly: true
                selectByMouse: true
                persistentSelection: true
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.WrapAnywhere
                font.family: "monospace"
                placeholderText: qsTr("No output yet")
            }
        }
    }

    NativeDialogs.FileDialog {
        id: saveDialog
        title: qsTr("Save Game Log")
        fileMode: NativeDialogs.FileDialog.SaveFile
        defaultSuffix: "log"
        onAccepted: dialog.controller.save_log(selectedFile)
    }

    Connections {
        target: dialog.controller

        function onLogChanged() {
            const text = dialog.controller.logText
            if (text.startsWith(log.text))
                log.insert(log.length, text.slice(log.length))
            else
                log.text = text
            if (follow.checked)
                log.cursorPosition = log.length
        }
    }
}
