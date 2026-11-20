pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "configDialog"

    required property QtObject controller

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(900, parent.width - 32)
    height: Math.min(680, parent.height - 32)
    title: controller.title
    modal: true
    closePolicy: controller.busy ? Popup.NoAutoClose : Popup.CloseOnEscape

    Connections {
        target: dialog.controller
        function onCloseRequested() { dialog.close() }
    }

    contentItem: ColumnLayout {
        spacing: 8

        RowLayout {
            Layout.fillWidth: true

            TabBar {
                id: tabs
                objectName: "configPages"
                Layout.fillWidth: true
                currentIndex: dialog.controller.page

                Repeater {
                    model: dialog.controller.pages

                    TabButton {
                        required property string modelData
                        required property int index

                        text: modelData
                        width: implicitWidth
                        onClicked: dialog.controller.select_page(index)
                    }
                }
            }

            TextField {
                objectName: "configSearch"
                visible: !dialog.controller.infoPage
                Layout.preferredWidth: 200
                placeholderText: qsTr("Search options")
                Accessible.name: qsTr("Search options")
                onTextEdited: dialog.controller.set_search(text)
            }

            Switch {
                objectName: "configShowAdvanced"
                visible: !dialog.controller.infoPage
                text: qsTr("Advanced")
                checked: dialog.controller.showAdvanced
                Accessible.name: qsTr("Show advanced options")
                onToggled: dialog.controller.set_show_advanced(checked)
            }
        }

        Label {
            Layout.fillWidth: true
            visible: text.length > 0
            text: dialog.controller.pageDescription
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            font.italic: true
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: !dialog.controller.ready
            indeterminate: true
            Accessible.name: qsTr("Loading options…")
        }

        GameInfoPage {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: dialog.controller.infoPage
            controller: dialog.controller
        }

        ListView {
            objectName: "configOptions"
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: !dialog.controller.infoPage
            clip: true
            model: dialog.controller.options
            reuseItems: false
            ScrollBar.vertical: ScrollBar {}

            section.property: "optionGroup"
            section.delegate: Label {
                required property string section

                width: ListView.view.width
                topPadding: 12
                bottomPadding: 4
                text: section
                font.bold: true
                visible: section.length > 0
                height: visible ? implicitHeight : 0
            }

            delegate: ConfigOption {
                width: ListView.view.width
                controller: dialog.controller
            }

            Label {
                anchors.centerIn: parent
                text: dialog.controller.emptyText
                visible: text.length > 0
            }
        }
    }

    footer: DialogButtonBox {
        Button {
            text: qsTr("Cancel")
            enabled: !dialog.controller.busy
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }

        Button {
            objectName: "configSave"
            text: qsTr("Save")
            enabled: dialog.controller.ready && dialog.controller.modified && !dialog.controller.busy
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.save()
        }
    }
}
