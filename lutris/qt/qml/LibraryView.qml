import QtQuick
import QtQuick.Controls

SplitView {
    id: library

    required property QtObject controller

    LibrarySidebar {
        SplitView.preferredWidth: 215
        SplitView.minimumWidth: 145
        SplitView.maximumWidth: 320
        controller: library.controller
    }

    Loader {
        SplitView.fillWidth: true
        sourceComponent: library.controller.gameCount === 0 ? emptyView
                         : library.controller.layout === "list" ? gameList : gameGrid
    }

    Component {
        id: emptyView
        Label {
            text: library.controller.emptyText
            padding: 24
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Component {
        id: gameList
        GameList { controller: library.controller }
    }

    Component {
        id: gameGrid
        GameGrid { controller: library.controller }
    }
}
