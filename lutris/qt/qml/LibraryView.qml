pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

SplitView {
    id: library

    required property QtObject controller

    // The view showing the library, whose current item is the selected game
    // The selected game's card or row, which the game bar shows the details of
    readonly property Item selectedGame: content.item?.selectedGame ?? null

    signal addMenuRequested(Item button)
    signal mainMenuRequested(Item button)

    LibrarySidebar {
        id: sidebar
        SplitView.preferredWidth: 236
        SplitView.minimumWidth: 180
        SplitView.maximumWidth: 340
        controller: library.controller
    }

    Item {
        SplitView.fillWidth: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            LibraryHeader {
                Layout.fillWidth: true
                controller: library.controller
                viewTitle: sidebar.currentTitle
                onAddMenuRequested: button => library.addMenuRequested(button)
                onMainMenuRequested: button => library.mainMenuRequested(button)
            }

            StoreSourceBar {
                Layout.fillWidth: true
                Layout.leftMargin: 20
                Layout.rightMargin: 20
                Layout.bottomMargin: 8
                controller: library.controller.storeSources
            }

            Loader {
                id: content
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceComponent: library.controller.gameCount === 0 ? emptyView
                                 : library.controller.layout === "list" ? gameList : gameGrid
            }

            GameBar {
                id: gameBar
                Layout.fillWidth: true
                controller: library.controller
                game: library.selectedGame
            }
        }

        StatusToast {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 16
            anchors.bottomMargin: gameBar.height + 16
            controller: library.controller
        }
    }

    Component {
        id: emptyView

        Item {
            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 48, 420)
                spacing: 12

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: 72
                    implicitHeight: 72
                    radius: 20
                    color: Theme.surface
                    border.color: Theme.border

                    Icon {
                        anchors.centerIn: parent
                        symbol: sidebar.currentIcon
                        size: 32
                        color: Theme.textSubtle
                    }
                }

                Label {
                    Layout.fillWidth: true
                    text: library.controller.emptyText
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    font.pointSize: Theme.largeSize
                    color: Theme.textMuted
                }
            }
        }
    }

    Component {
        id: gameList

        GameList {
            controller: library.controller
            onMenuRequested: gameBar.showActions(true)
        }
    }

    Component {
        id: gameGrid

        GameGrid {
            controller: library.controller
            onMenuRequested: gameBar.showActions(true)
        }
    }
}
