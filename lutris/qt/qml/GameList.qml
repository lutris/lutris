pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

ColumnLayout {
    id: list

    required property QtObject controller
    readonly property bool showDetails: width >= 760
    readonly property bool showPlatform: width >= 520
    readonly property Item selectedGame: rows.currentItem
    // The columns after the name, which the header and rows share
    readonly property var columns: [
        { key: "", title: qsTr("Runner"), width: 96, visible: showPlatform },
        { key: "", title: qsTr("Platform"), width: 96, visible: showPlatform },
        { key: "year", title: qsTr("Year"), width: 58, visible: showDetails },
        { key: "lastplayed", title: qsTr("Last Played"), width: 104, visible: showDetails },
        { key: "installed_at", title: qsTr("Installed At"), width: 104, visible: showDetails },
        { key: "playtime", title: qsTr("Play Time"), width: 110, visible: showDetails }
    ]

    signal menuRequested()

    spacing: 0

    component ColumnHeader: AbstractButton {
        id: column

        required property var modelData
        readonly property bool sorted: list.controller.sortKey === modelData.key

        Layout.preferredWidth: modelData.width
        visible: modelData.visible
        enabled: modelData.key.length > 0
        text: modelData.title
        hoverEnabled: true
        onClicked: list.controller.sort_by_column(modelData.key)

        contentItem: RowLayout {
            spacing: 4

            Label {
                text: column.text.toUpperCase()
                font.pointSize: Theme.smallSize * 0.9
                font.weight: Font.DemiBold
                font.letterSpacing: 0.6
                color: column.sorted ? Theme.accentText : column.hovered ? Theme.text : Theme.textSubtle
                elide: Text.ElideRight
                Layout.maximumWidth: column.modelData.width - 16
            }

            Icon {
                visible: column.sorted
                symbol: list.controller.sortReversed ? "arrow-up" : "arrow-down"
                size: 12
                color: Theme.accentText
            }

            Item { Layout.fillWidth: true }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 32
        Layout.rightMargin: 32
        Layout.topMargin: 4
        Layout.bottomMargin: 8
        spacing: 10

        ColumnHeader {
            Layout.fillWidth: true
            modelData: { "key": "name", "title": qsTr("Name"), "width": 180, "visible": true }
        }

        Repeater {
            model: list.columns
            delegate: ColumnHeader {}
        }
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.leftMargin: 20
        Layout.rightMargin: 20
        implicitHeight: 1
        color: Theme.border
    }

    ListView {
        id: rows
        objectName: "libraryList"
        Layout.fillHeight: true
        Layout.fillWidth: true
        leftMargin: 20
        rightMargin: 20
        topMargin: 6
        bottomMargin: 12
        clip: true
        model: list.controller.gamesModel
        currentIndex: list.controller.selectedRow
        reuseItems: true
        activeFocusOnTab: true
        keyNavigationEnabled: false
        boundsBehavior: Flickable.StopAtBounds
        spacing: 2
        Accessible.name: qsTr("Game library")

        Keys.onUpPressed: list.controller.select_game(currentIndex < 0 ? 0 : currentIndex - 1)
        Keys.onDownPressed: list.controller.select_game(currentIndex + 1)
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                list.controller.select_game(event.key === Qt.Key_Home ? 0 : count - 1)
                event.accepted = true
            } else if (event.key === Qt.Key_Menu) {
                list.menuRequested()
                event.accepted = true
            }
        }
        Keys.onReturnPressed: list.controller.play()
        Keys.onEnterPressed: list.controller.play()

        ScrollBar.vertical: ScrollBar {}

        delegate: GameListRow {
            width: rows.width - rows.leftMargin - rows.rightMargin
            columns: list.columns
            placeholder: list.controller.placeholderArtwork
            selected: rows.currentIndex === index
            keyboardFocus: selected && rows.activeFocus
            onClicked: {
                rows.forceActiveFocus()
                list.controller.select_game(index)
            }
            onDoubleClicked: {
                list.controller.select_game(index)
                list.controller.play()
            }
            onMenuRequested: {
                rows.forceActiveFocus()
                list.controller.select_game(index)
                list.menuRequested()
            }
        }
    }
}
