pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: page

    required property QtObject controller
    required property QtObject configuration

    spacing: 8
    Component.onCompleted: controller.open()

    RowLayout {
        Layout.fillWidth: true
        visible: page.controller.proton

        Button {
            text: qsTr("Back to Runners")
            enabled: !page.controller.busy
            onClicked: page.controller.open()
        }

        Item { Layout.fillWidth: true }

        Button {
            text: qsTr("Check for Releases")
            enabled: !page.controller.busy
            onClicked: page.controller.show_proton()
        }
    }

    Label {
        Layout.fillWidth: true
        visible: page.controller.proton
        text: qsTr("GE-Proton (Latest) is downloaded by umu when needed. Install a specific release to select it in Runner Options.")
        wrapMode: Text.WordWrap
    }

    ListView {
        id: entries
        objectName: "runnerCatalog"
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: 2
        model: page.controller.entries
        ScrollBar.vertical: ScrollBar {}

        delegate: RowLayout {
            id: entry

            required property var modelData

            width: entries.width - 16
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Label {
                    Layout.fillWidth: true
                    text: entry.modelData.label
                    font.bold: true
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }

                Label {
                    Layout.fillWidth: true
                    text: entry.modelData.description
                    visible: text.length > 0
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                }
            }

            Label {
                text: entry.modelData.installed ? qsTr("Installed") : qsTr("Not installed")
            }

            Button {
                objectName: "runnerConfigure_" + entry.modelData.key
                visible: entry.modelData.canConfigure
                enabled: !page.controller.busy
                text: qsTr("Configure…")
                Accessible.name: qsTr("Configure %1").arg(entry.modelData.label)
                onClicked: page.configuration.open_runner(entry.modelData.key, entry.modelData.label)
            }

            Button {
                objectName: "runnerVersions_" + entry.modelData.key
                visible: entry.modelData.manageProton
                enabled: !page.controller.busy
                text: qsTr("Manage GE-Proton")
                onClicked: page.controller.show_proton()
            }

            Button {
                objectName: "runnerInstall_" + entry.modelData.key
                visible: entry.modelData.canInstall
                enabled: !page.controller.busy
                text: qsTr("Install")
                Accessible.name: qsTr("Install %1").arg(entry.modelData.label)
                onClicked: page.controller.install(entry.modelData.key)
            }

            Button {
                objectName: "runnerRemove_" + entry.modelData.key
                visible: entry.modelData.canRemove
                enabled: !page.controller.busy
                text: qsTr("Remove…")
                Accessible.name: qsTr("Remove %1").arg(entry.modelData.label)
                onClicked: page.controller.remove(entry.modelData.key)
            }
        }

        Label {
            anchors.centerIn: parent
            visible: !page.controller.busy && entries.count === 0
            text: page.controller.proton ? qsTr("No GE-Proton builds found") : qsTr("No runners found")
        }
    }

    Label {
        Layout.fillWidth: true
        visible: text.length > 0
        text: page.controller.message
        wrapMode: Text.WordWrap
    }

    ProgressBar {
        Layout.fillWidth: true
        visible: page.controller.busy
        indeterminate: visible && page.controller.fraction < 0
        value: Math.max(0, page.controller.fraction)
        Accessible.name: page.controller.message
    }
}
