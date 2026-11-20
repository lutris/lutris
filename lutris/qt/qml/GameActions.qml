pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

ToolButton {
    id: actions
    objectName: "libraryGameActions"

    required property QtObject controller
    property string targetGameId: ""
    property string targetGameName: ""
    property bool targetCanPlay: false
    property bool targetInstalled: false

    text: qsTr("Game Actions")
    enabled: controller.selectedGameId.length > 0
    onClicked: {
        targetGameId = controller.selectedGameId
        targetGameName = controller.selectedGameName
        targetCanPlay = controller.canPlay
        targetInstalled = controller.selectedGameInstalled
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
            text: qsTr("Play with Launch Options")
            enabled: actions.targetCanPlay
            onTriggered: actions.controller.launch(actions.targetGameId, true)
        }

        MenuItem {
            objectName: "showGameLogs"
            text: qsTr("Show Logs…")
            enabled: actions.targetInstalled
            onTriggered: {
                actions.controller.gameLog.open_log(actions.targetGameId)
                logLoader.active = true
            }
        }

        MenuItem {
            objectName: "manageGameShortcuts"
            text: qsTr("Manage Shortcuts…")
            enabled: actions.targetInstalled
            onTriggered: {
                actions.controller.gameShortcuts.open_shortcuts(actions.targetGameId)
                shortcutsLoader.active = true
            }
        }

        MenuItem {
            text: qsTr("Browse Files")
            onTriggered: actions.controller.browse_files(actions.targetGameId)
        }

        MenuSeparator {}

        MenuItem {
            objectName: "moveGame"
            text: qsTr("Move Game…")
            enabled: actions.targetInstalled && actions.controller.canMaintain
            onTriggered: {
                actions.controller.gameMaintenance.open_maintenance(actions.targetGameId)
                moveLoader.active = true
            }
        }

        MenuItem {
            objectName: "uninstallGame"
            text: actions.targetInstalled ? qsTr("Uninstall Game…") : qsTr("Remove from Library…")
            enabled: actions.controller.canMaintain
            onTriggered: {
                actions.controller.gameMaintenance.open_maintenance(actions.targetGameId)
                uninstallLoader.active = true
            }
        }
    }

    Loader {
        id: moveLoader
        active: false
        sourceComponent: MoveGameDialog {
            controller: actions.controller.gameMaintenance
            gameName: actions.targetGameName
            onClosed: {
                controller.close_maintenance()
                moveLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as MoveGameDialog).open()
    }

    Loader {
        id: uninstallLoader
        active: false
        sourceComponent: UninstallGameDialog {
            controller: actions.controller.gameMaintenance
            gameName: actions.targetGameName
            installed: actions.targetInstalled
            onClosed: {
                controller.close_maintenance()
                uninstallLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as UninstallGameDialog).open()
    }

    Loader {
        id: logLoader
        active: false
        sourceComponent: GameLogDialog {
            controller: actions.controller.gameLog
            gameName: actions.targetGameName
            onClosed: {
                controller.close_log()
                logLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as GameLogDialog).open()
    }

    Loader {
        id: shortcutsLoader
        active: false
        sourceComponent: GameShortcutsDialog {
            controller: actions.controller.gameShortcuts
            gameName: actions.targetGameName
            onClosed: shortcutsLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) (item as GameShortcutsDialog).open()
    }

    Loader {
        id: categoryLoader
        active: false
        sourceComponent: CategoryDialog {
            controller: actions.controller
            targetGameId: actions.targetGameId
            onClosed: categoryLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) (item as CategoryDialog).open()
    }
}
