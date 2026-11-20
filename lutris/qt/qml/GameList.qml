import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: list

    required property QtObject controller
    readonly property bool showDetails: width >= 710
    readonly property bool showPlatform: width >= 470

    spacing: 0

    RowLayout {
        Layout.fillWidth: true
        spacing: 6

        Repeater {
            model: [
                { key: "name", title: qsTr("Name"), width: 180, visible: true },
                { key: "", title: qsTr("Runner"), width: 88, visible: list.showPlatform },
                { key: "", title: qsTr("Platform"), width: 88, visible: list.showPlatform },
                { key: "year", title: qsTr("Year"), width: 58, visible: list.showDetails },
                { key: "lastplayed", title: qsTr("Last Played"), width: 100, visible: list.showDetails },
                { key: "installed_at", title: qsTr("Installed At"), width: 100, visible: list.showDetails },
                { key: "playtime", title: qsTr("Play Time"), width: 105, visible: list.showDetails }
            ]
            delegate: ToolButton {
                required property var modelData
                Layout.preferredWidth: modelData.width
                Layout.fillWidth: modelData.key === "name"
                visible: modelData.visible
                text: modelData.title
                enabled: modelData.key.length > 0
                highlighted: list.controller.sortKey === modelData.key
                onClicked: list.controller.sort_by_column(modelData.key)
            }
        }
    }

    ListView {
        id: rows
        objectName: "libraryList"
        Layout.fillHeight: true
        Layout.fillWidth: true
        clip: true
        model: list.controller.gamesModel
        currentIndex: list.controller.selectedRow
        reuseItems: true
        activeFocusOnTab: true
        keyNavigationEnabled: false
        boundsBehavior: Flickable.StopAtBounds
        Accessible.name: qsTr("Game library")

        Keys.onUpPressed: list.controller.select_game(currentIndex < 0 ? 0 : currentIndex - 1)
        Keys.onDownPressed: list.controller.select_game(currentIndex + 1)
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                list.controller.select_game(event.key === Qt.Key_Home ? 0 : count - 1)
                event.accepted = true
            }
        }
        Keys.onReturnPressed: list.controller.play()
        Keys.onEnterPressed: list.controller.play()

        ScrollBar.vertical: ScrollBar {}

        delegate: GameListRow {
            width: rows.width
            showDetails: list.showDetails
            showPlatform: list.showPlatform
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
        }
    }
}
