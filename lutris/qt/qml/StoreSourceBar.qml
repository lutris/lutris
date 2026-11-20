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
            visible: bar.controller.busy || (Boolean(bar.source.online) && !bar.source.canSignIn && !bar.source.signedIn)
            text: bar.controller.busy ? qsTr("Working…") : qsTr("Browser sign-in unavailable")
        }

        ToolButton {
            visible: bar.controller.launchers.length > 1
            enabled: !bar.controller.busy
            text: qsTr("Choose Launcher")
            onClicked: launcherMenu.open()

            Menu {
                id: launcherMenu

                Repeater {
                    model: bar.controller.launchers

                    MenuItem {
                        required property var modelData
                        required property int index

                        text: modelData.label
                        checkable: true
                        checked: index === 0
                        onTriggered: bar.controller.choose_launcher(modelData.id)
                    }
                }
            }
        }

        Button {
            visible: bar.controller.launchers.length > 0
            enabled: !bar.controller.busy
            text: qsTr("Run Launcher")
            onClicked: bar.controller.run_launcher()
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
