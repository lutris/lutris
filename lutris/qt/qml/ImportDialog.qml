pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog

    required property QtObject controller
    property bool scanningRoms: false

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(600, parent.width - 32)
    height: Math.min(460, parent.height - 32)
    title: scanningRoms ? qsTr("Import ROMs") : qsTr("Import from Playtron")
    closePolicy: controller.busy ? Popup.NoAutoClose : Popup.CloseOnEscape
    modal: true

    contentItem: ColumnLayout {
        Label {
            Layout.fillWidth: true
            visible: dialog.controller.busy
            text: qsTr("Scanning for games…")
        }

        ListView {
            id: results
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: dialog.controller.results
            ScrollBar.vertical: ScrollBar {}

            delegate: Label {
                required property string modelData

                width: results.width - 16
                padding: 6
                text: modelData
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
            }
        }

        Button {
            Layout.alignment: Qt.AlignRight
            enabled: dialog.scanningRoms || !dialog.controller.busy
            text: dialog.controller.busy ? qsTr("Stop after current file") : qsTr("Close")
            onClicked: dialog.controller.busy ? dialog.controller.stop() : dialog.close()
        }
    }
}
