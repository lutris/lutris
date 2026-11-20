import QtQuick
import QtQuick.Controls

ToolButton {
    id: actions
    objectName: "libraryGameActions"

    required property QtObject controller
    property string targetGameId: ""

    text: qsTr("Game Actions")
    enabled: controller.selectedGameId.length > 0
    onClicked: {
        targetGameId = controller.selectedGameId
        controller.load_organization(targetGameId)
        gameMenu.open()
    }

    Menu {
        id: gameMenu
        objectName: "libraryGameMenu"
        y: actions.height

        MenuItem {
            objectName: "toggleFavorite"
            text: actions.controller.favorite ? qsTr("Remove from Favorites") : qsTr("Add to Favorites")
            enabled: actions.controller.organizationReady
            onTriggered: actions.controller.set_favorite(actions.targetGameId, !actions.controller.favorite)
        }

        MenuItem {
            text: actions.controller.hidden ? qsTr("Unhide Game") : qsTr("Hide Game")
            enabled: actions.controller.organizationReady
            onTriggered: actions.controller.set_hidden(actions.targetGameId, !actions.controller.hidden)
        }

        MenuItem {
            objectName: "editGameCategories"
            text: qsTr("Edit Categories…")
            onTriggered: categoryLoader.active = true
        }

        MenuSeparator {}

        MenuItem {
            text: qsTr("Browse Files")
            onTriggered: actions.controller.browse_files(actions.targetGameId)
        }
    }

    Loader {
        id: categoryLoader
        active: false
        sourceComponent: CategoryDialog {
            controller: actions.controller
            targetGameId: actions.targetGameId
            onClosed: categoryLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) item.open()
    }
}
