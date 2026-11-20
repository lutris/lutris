pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

Dialog {
    id: dialog
    objectName: "configDialog"

    required property QtObject controller

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(920, parent.width - 48)
    height: Math.min(700, parent.height - 48)
    title: controller.title
    modal: true
    closePolicy: controller.busy ? Popup.NoAutoClose : Popup.CloseOnEscape

    Connections {
        target: dialog.controller
        function onCloseRequested() { dialog.close() }
    }

    contentItem: ColumnLayout {
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            TabBar {
                id: tabs
                objectName: "configPages"
                Layout.maximumWidth: parent.width - (search.visible ? search.width + advanced.width + 20 : 0)
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

            Item { Layout.fillWidth: true }

            TextField {
                id: search
                objectName: "configSearch"
                visible: !dialog.controller.infoPage
                Layout.preferredWidth: 220
                leftPadding: 34
                placeholderText: qsTr("Search options")
                Accessible.name: qsTr("Search options")
                onTextEdited: dialog.controller.set_search(text)

                Icon {
                    x: 11
                    anchors.verticalCenter: parent.verticalCenter
                    symbol: "search"
                    size: 16
                    color: Theme.textSubtle
                }
            }

            Switch {
                id: advanced
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
            font.pointSize: Theme.smallSize
            color: Theme.textMuted
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
            spacing: 2
            rightMargin: 10
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}

            section.property: "optionGroup"
            section.delegate: ColumnLayout {
                required property string section

                width: ListView.view.width - ListView.view.rightMargin
                visible: section.length > 0
                height: visible ? implicitHeight : 0
                spacing: 6

                Label {
                    Layout.fillWidth: true
                    Layout.topMargin: 18
                    Layout.leftMargin: 10
                    text: parent.section.toUpperCase()
                    font.pointSize: Theme.smallSize * 0.92
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.8
                    color: Theme.accentText
                    elide: Text.ElideRight
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 4
                    implicitHeight: 1
                    color: Theme.border
                }
            }

            delegate: ConfigOption {
                width: ListView.view.width - ListView.view.rightMargin
                controller: dialog.controller
            }

            Label {
                anchors.centerIn: parent
                width: parent.width - 48
                text: dialog.controller.emptyText
                visible: text.length > 0
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                color: Theme.textMuted
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
            highlighted: true
            text: qsTr("Save")
            enabled: dialog.controller.ready && dialog.controller.modified && !dialog.controller.busy
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.save()
        }
    }
}
