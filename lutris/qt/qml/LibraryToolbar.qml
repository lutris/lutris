import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ToolBar {
    id: toolbar

    required property QtObject controller
    padding: 8

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: search.forceActiveFocus()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 8

        ToolButton {
            objectName: "playGame"
            text: qsTr("Play")
            enabled: toolbar.controller.canPlay
            onClicked: toolbar.controller.play()
        }

        ToolButton {
            objectName: "stopGame"
            text: qsTr("Stop")
            enabled: toolbar.controller.canStop
            onClicked: toolbar.controller.stop()
        }

        GameActions { controller: toolbar.controller }

        TextField {
            id: search
            objectName: "librarySearch"
            Layout.fillWidth: true
            Layout.minimumWidth: 120
            placeholderText: toolbar.controller.searchHint
            Accessible.name: qsTr("Search games")
            selectByMouse: true
            onTextEdited: toolbar.controller.set_search(text)
            Keys.onEscapePressed: {
                clear()
                toolbar.controller.set_search("")
            }
        }

        CheckBox {
            text: qsTr("Installed only")
            checked: toolbar.controller.installedOnly
            onToggled: toolbar.controller.set_installed_only(checked)
        }

        ToolButton {
            id: sortButton
            text: qsTr("Sort By")
            onClicked: sortMenu.open()

            Menu {
                id: sortMenu
                objectName: "librarySortMenu"
                y: sortButton.height
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
                        checked: toolbar.controller.sortKey === modelData.key
                        ButtonGroup.group: sortGroup
                        onTriggered: toolbar.controller.set_sort(modelData.key)
                    }
                }

                MenuSeparator {}

                MenuItem {
                    text: qsTr("Reverse Order")
                    checkable: true
                    checked: toolbar.controller.sortReversed
                    onTriggered: toolbar.controller.reverse_sort()
                }
            }
        }

        ToolButton {
            id: viewButton
            visible: toolbar.controller.showMedia
            text: qsTr("View")
            onClicked: viewMenu.open()

            Menu {
                id: viewMenu
                objectName: "libraryViewMenu"
                y: viewButton.height
                ButtonGroup { id: viewGroup }

                Repeater {
                    model: [
                        { key: "covers", title: qsTr("Covers") },
                        { key: "banners", title: qsTr("Banners") },
                        { key: "list", title: qsTr("List") }
                    ]
                    delegate: MenuItem {
                        required property var modelData
                        text: modelData.title
                        checkable: true
                        checked: toolbar.controller.layout === modelData.key
                        ButtonGroup.group: viewGroup
                        onTriggered: toolbar.controller.set_layout(modelData.key)
                    }
                }

                MenuSeparator {}

                MenuItem {
                    text: qsTr("Update Game Artwork")
                    enabled: !toolbar.controller.updatingArtwork
                    onTriggered: toolbar.controller.update_artwork()
                }
            }
        }
    }
}
