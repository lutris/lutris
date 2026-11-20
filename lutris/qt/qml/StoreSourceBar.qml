pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

// The store whose games the library shows, with its account and launcher controls
Frame {
    id: bar

    required property QtObject controller
    readonly property var source: controller.source
    readonly property string statusText: controller.busy ? qsTr("Working…")
                                    : source.signedIn ? qsTr("Signed in")
                                    : Boolean(source.online) && !source.canSignIn ? qsTr("Browser sign-in unavailable")
                                    : Boolean(source.online) ? qsTr("Not signed in") : qsTr("Local library")

    visible: Boolean(source.name)
    padding: 10
    leftPadding: 14

    contentItem: RowLayout {
        spacing: 8

        Rectangle {
            implicitWidth: 36
            implicitHeight: 36
            radius: Theme.radius
            color: Theme.accentSubtle

            Icon {
                anchors.centerIn: parent
                symbol: "store"
                size: 18
                color: Theme.accentText
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 4
            spacing: 0

            Label {
                Layout.fillWidth: true
                text: bar.source.name ?? ""
                textFormat: Text.PlainText
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Rectangle {
                    implicitWidth: 7
                    implicitHeight: 7
                    radius: 3.5
                    color: bar.controller.busy ? Theme.warning : bar.source.signedIn ? Theme.success : Theme.textSubtle
                }

                Label {
                    Layout.fillWidth: true
                    text: bar.statusText
                    font.pointSize: Theme.smallSize
                    color: Theme.textMuted
                    elide: Text.ElideRight
                }
            }
        }

        BusyIndicator {
            implicitWidth: 28
            implicitHeight: 28
            padding: 2
            visible: running
            running: bar.controller.busy
        }

        ToolButton {
            visible: bar.controller.launchers.length > 1
            enabled: !bar.controller.busy
            text: qsTr("Choose Launcher")
            icon.source: Theme.icon("chevron-down")
            onClicked: launcherMenu.popup(this, 0, height + 4)

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
            icon.source: Theme.icon("external")
            onClicked: bar.controller.run_launcher()
        }

        Button {
            objectName: "storeSync"
            visible: Boolean(bar.source.name) && (!bar.source.online || bar.source.signedIn)
            enabled: !bar.controller.busy
            text: qsTr("Sync Library")
            icon.source: Theme.icon("refresh")
            onClicked: bar.controller.sync()
        }

        Button {
            objectName: "storeSignIn"
            visible: Boolean(bar.source.canSignIn) && !bar.source.signedIn
            enabled: !bar.controller.busy
            highlighted: true
            text: qsTr("Sign In…")
            icon.source: Theme.icon("sign-in")
            onClicked: bar.controller.sign_in()
        }

        ToolButton {
            objectName: "storeDisconnect"
            visible: Boolean(bar.source.signedIn)
            enabled: !bar.controller.busy
            icon.source: Theme.icon("sign-out")
            Accessible.name: qsTr("Disconnect")
            ToolTip.visible: hovered
            ToolTip.text: qsTr("Disconnect")
            onClicked: bar.controller.disconnect_store()
        }
    }
}
