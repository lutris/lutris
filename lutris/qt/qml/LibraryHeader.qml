pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

// The current view's title, with the search, filter, sort and layout controls of the library
ToolBar {
    id: header

    required property QtObject controller
    required property string viewTitle
    readonly property bool compact: width < 760

    signal addMenuRequested(Item button)
    signal mainMenuRequested(Item button)

    leftPadding: 20
    rightPadding: 14
    topPadding: 14
    bottomPadding: 12

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: search.forceActiveFocus()
    }

    contentItem: RowLayout {
        spacing: 6

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 60
            spacing: 0

            Label {
                Layout.fillWidth: true
                text: header.viewTitle
                textFormat: Text.PlainText
                font.pointSize: Theme.headingSize * 0.85
                font.weight: Font.Bold
                elide: Text.ElideRight
            }

            Label {
                Layout.fillWidth: true
                text: header.controller.gameCount === 1 ? qsTr("1 game")
                                                         : qsTr("%1 games").arg(header.controller.gameCount)
                font.pointSize: Theme.smallSize
                color: Theme.textMuted
                elide: Text.ElideRight
            }
        }

        TextField {
            id: search
            objectName: "librarySearch"
            // Search shrinks before the buttons beside it do
            Layout.fillWidth: true
            Layout.preferredWidth: 280
            Layout.maximumWidth: 320
            Layout.minimumWidth: 100
            leftPadding: 34
            placeholderText: header.controller.searchHint
            Accessible.name: qsTr("Search games")
            onTextEdited: header.controller.set_search(text)
            Keys.onEscapePressed: {
                clear()
                header.controller.set_search("")
            }

            Icon {
                x: 11
                anchors.verticalCenter: parent.verticalCenter
                symbol: "search"
                size: 16
                color: Theme.textSubtle
            }

            ToolButton {
                anchors.right: parent.right
                anchors.rightMargin: 3
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: 28
                implicitHeight: 28
                padding: 5
                visible: search.length > 0
                icon.source: Theme.icon("close")
                icon.width: 14
                icon.height: 14
                Accessible.name: qsTr("Clear search")
                onClicked: {
                    search.clear()
                    header.controller.set_search("")
                }
            }
        }

        ToolButton {
            objectName: "installedOnly"
            Layout.leftMargin: 4
            checkable: true
            checked: header.controller.installedOnly
            text: header.compact ? "" : qsTr("Installed")
            icon.source: Theme.icon(checked ? "check" : "download")
            Accessible.name: qsTr("Installed only")
            ToolTip.visible: hovered
            ToolTip.text: checked ? qsTr("Showing installed games only") : qsTr("Show installed games only")
            onToggled: header.controller.set_installed_only(checked)
        }

        ToolButton {
            id: sortButton
            icon.source: Theme.icon("sort")
            Accessible.name: qsTr("Sort By")
            ToolTip.visible: hovered && !sortMenu.visible
            ToolTip.text: qsTr("Sort By")
            onClicked: sortMenu.popup(sortButton, 0, sortButton.height + 4)

            Menu {
                id: sortMenu
                objectName: "librarySortMenu"

                ButtonGroup { id: sortGroup }

                Repeater {
                    model: [
                        { key: "name", title: qsTr("Name") },
                        { key: "year", title: qsTr("Year") },
                        { key: "lastplayed", title: qsTr("Last Played") },
                        { key: "installed_at", title: qsTr("Installed At") },
                        { key: "playtime", title: qsTr("Play Time") }
                    ]
                    delegate: MenuItem {
                        required property var modelData
                        text: modelData.title
                        checkable: true
                        checked: header.controller.sortKey === modelData.key
                        ButtonGroup.group: sortGroup
                        onTriggered: header.controller.set_sort(modelData.key)
                    }
                }

                MenuSeparator {}

                MenuItem {
                    text: qsTr("Reverse Order")
                    checkable: true
                    checked: header.controller.sortReversed
                    onTriggered: header.controller.reverse_sort()
                }
            }
        }

        // The layouts, as a segmented control
        Rectangle {
            objectName: "libraryLayouts"
            visible: header.controller.showMedia
            implicitWidth: layouts.implicitWidth + 6
            implicitHeight: layouts.implicitHeight + 6
            radius: Theme.radius
            color: Theme.dark ? Theme.field : Theme.controlPressed
            border.color: Theme.border

            Row {
                id: layouts
                anchors.centerIn: parent
                spacing: 2

                Repeater {
                    model: [
                        { key: "covers", title: qsTr("Covers") },
                        { key: "banners", title: qsTr("Banners") },
                        { key: "list", title: qsTr("List") }
                    ]
                    delegate: ToolButton {
                        id: layoutButton

                        required property var modelData
                        readonly property bool current: header.controller.layout === modelData.key

                        implicitWidth: 32
                        implicitHeight: 28
                        padding: 5
                        icon.source: Theme.icon(modelData.key)
                        icon.color: current ? Theme.text : Theme.textMuted
                        Accessible.name: modelData.title
                        ToolTip.visible: hovered
                        ToolTip.text: modelData.title
                        onClicked: header.controller.set_layout(modelData.key)

                        background: Rectangle {
                            radius: Theme.radiusSmall
                            color: layoutButton.current ? Theme.raised : layoutButton.hovered ? Theme.hover : "transparent"
                            border.color: layoutButton.current ? Theme.borderStrong : "transparent"
                        }
                    }
                }
            }
        }

        ToolSeparator { visible: !header.compact }

        Button {
            id: addButton
            objectName: "addMenuButton"
            highlighted: true
            text: header.compact ? "" : qsTr("Add")
            icon.source: Theme.icon("plus")
            Accessible.name: qsTr("Add games")
            onClicked: header.addMenuRequested(addButton)
        }

        ToolButton {
            id: menuButton
            objectName: "mainMenuButton"
            icon.source: Theme.icon("menu")
            Accessible.name: qsTr("Main menu")
            ToolTip.visible: hovered
            ToolTip.text: qsTr("Main menu")
            onClicked: header.mainMenuRequested(menuButton)
        }
    }
}
