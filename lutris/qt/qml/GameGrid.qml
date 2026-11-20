import QtQuick
import QtQuick.Controls

GridView {
    id: grid
    objectName: "libraryGrid"

    required property QtObject controller
    readonly property bool banners: controller.layout === "banners"
    readonly property bool showTitle: !controller.preferences.hideGameTitles
    readonly property int columns: Math.max(1, Math.floor((width - leftMargin - rightMargin) / (banners ? 270 : 178)))
    readonly property Item selectedGame: currentItem

    signal menuRequested()

    leftMargin: 12
    rightMargin: 12
    topMargin: 4
    bottomMargin: 16
    cellWidth: Math.floor((width - leftMargin - rightMargin) / columns)
    // A card's padding and title around artwork in its layout's shape
    cellHeight: Math.ceil((cellWidth - 16) * (banners ? 69 / 184 : 4 / 3)) + (showTitle ? 46 : 22)
    model: controller.gamesModel
    currentIndex: controller.selectedRow
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    keyNavigationEnabled: false
    activeFocusOnTab: true
    Accessible.name: qsTr("Game library")

    Keys.onLeftPressed: controller.select_game(currentIndex < 0 ? 0 : currentIndex - 1)
    Keys.onRightPressed: controller.select_game(currentIndex + 1)
    Keys.onUpPressed: controller.select_game(currentIndex < 0 ? 0 : Math.max(0, currentIndex - columns))
    Keys.onDownPressed: controller.select_game(currentIndex < 0 ? 0 : Math.min(count - 1, currentIndex + columns))
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
            controller.select_game(event.key === Qt.Key_Home ? 0 : count - 1)
            event.accepted = true
        } else if (event.key === Qt.Key_Menu) {
            menuRequested()
            event.accepted = true
        }
    }
    Keys.onReturnPressed: controller.play()
    Keys.onEnterPressed: controller.play()

    ScrollBar.vertical: ScrollBar {}

    delegate: GameCard {
        width: grid.cellWidth
        height: grid.cellHeight
        banners: grid.banners
        selected: grid.currentIndex === index
        keyboardFocus: selected && grid.activeFocus
        placeholder: grid.controller.placeholderArtwork
        showTitle: grid.showTitle
        showBadges: !grid.controller.preferences.hideBadges
        onClicked: {
            grid.forceActiveFocus()
            grid.controller.select_game(index)
        }
        onDoubleClicked: {
            grid.controller.select_game(index)
            grid.controller.play()
        }
        onMenuRequested: {
            grid.forceActiveFocus()
            grid.controller.select_game(index)
            grid.menuRequested()
        }
    }
}
