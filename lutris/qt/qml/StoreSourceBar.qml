import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ToolBar {
    id: bar

    required property QtObject controller
    readonly property var source: controller.source

    visible: Boolean(source.name)

    contentItem: RowLayout {
        spacing: 8

        Label {
            Layout.fillWidth: true
            text: bar.source.name ?? ""
            textFormat: Text.PlainText
            font.bold: true
            elide: Text.ElideRight
        }

        Label {
            visible: bar.controller.busy || (bar.source.online && !bar.source.canSignIn && !bar.source.signedIn)
            text: bar.controller.busy ? qsTr("Working…") : qsTr("Browser sign-in unavailable")
        }

        Button {
            objectName: "storeSignIn"
            visible: Boolean(bar.source.canSignIn) && !bar.source.signedIn
            enabled: !bar.controller.busy
            text: qsTr("Sign In…")
            onClicked: bar.controller.sign_in()
        }

        Button {
            objectName: "storeSync"
            visible: Boolean(bar.source.name) && (!bar.source.online || bar.source.signedIn)
            enabled: !bar.controller.busy
            text: qsTr("Sync Library")
            onClicked: bar.controller.sync()
        }

        Button {
            objectName: "storeDisconnect"
            visible: Boolean(bar.source.signedIn)
            enabled: !bar.controller.busy
            text: qsTr("Disconnect")
            onClicked: bar.controller.disconnect_store()
        }
    }
}
