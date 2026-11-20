import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "issueReportDialog"

    required property QtObject controller

    title: qsTr("Save Issue Report")
    modal: true
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(560, parent.width - 32)
    standardButtons: Dialog.Save | Dialog.Cancel
    onAccepted: target.open()

    contentItem: ColumnLayout {
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Describe the problem. The report includes system information and is saved locally so you can review it before sharing.")
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 180

            TextArea {
                id: description
                Accessible.name: qsTr("Problem description")
                wrapMode: TextEdit.Wrap
            }
        }
    }

    NativeDialogs.FileDialog {
        id: target
        title: qsTr("Save Issue Report")
        fileMode: NativeDialogs.FileDialog.SaveFile
        nameFilters: [qsTr("JSON reports (*.json)")]
        defaultSuffix: "json"
        onAccepted: {
            dialog.controller.save_issue_report(selectedFile, description.text)
            description.clear()
        }
    }

    Connections {
        target: dialog.controller
        function onIssueReportRequested() { dialog.open() }
    }
}
