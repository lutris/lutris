pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

SplitView {
    id: library

    required property QtObject controller

    LibrarySidebar {
        SplitView.preferredWidth: 215
        SplitView.minimumWidth: 145
        SplitView.maximumWidth: 320
        controller: library.controller
    }

    ColumnLayout {
        SplitView.fillWidth: true
        spacing: 0

        StoreSourceBar {
            Layout.fillWidth: true
            controller: library.controller.storeSources
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: library.controller.gameCount === 0 ? emptyView
                             : library.controller.layout === "list" ? gameList : gameGrid
        }
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
