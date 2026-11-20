pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import LutrisStyle

ToolButton {
    id: actions
    objectName: "libraryGameActions"

    required property QtObject controller
    property string targetGameId: ""
    property string targetGameName: ""
    property string targetService: ""
    property string targetAppId: ""
    property bool targetCanPlay: false
    property bool targetInstalled: false
    property bool targetCanMaintain: false
    property bool targetCanLinkLocalGame: false
    property bool targetCanInstall: false
    property bool targetCanUpdate: false
    property bool targetCanInstallDlc: false

    icon.source: Theme.icon("more")
    Accessible.name: qsTr("Game Actions")
    ToolTip.visible: hovered && !gameMenu.visible
    ToolTip.text: qsTr("Game Actions")
    enabled: controller.selectedGameId.length > 0 || controller.canInstall
    onClicked: showMenu(false)

    // Opens the menu of the selected game, under the pointer or above this button
    function showMenu(atPointer: bool): void {
        if (!enabled)
            return
        targetGameId = controller.selectedGameId
        targetGameName = controller.selectedGameName
        targetService = controller.selectedGameService
        targetAppId = controller.selectedGameAppId
        targetCanPlay = controller.canPlay
        targetInstalled = controller.selectedGameInstalled
        targetCanMaintain = controller.canMaintain
        targetCanLinkLocalGame = controller.canLinkLocalGame
        targetCanInstall = controller.canInstall
        targetCanUpdate = controller.canUpdateGame
        targetCanInstallDlc = controller.canInstallDlc
        if (targetGameId.length > 0)
            controller.load_organization(targetGameId)
        if (atPointer)
            gameMenu.popup()
        else
            gameMenu.popup(actions, actions.width - gameMenu.width, -gameMenu.implicitHeight - 6)
    }

    function openInstaller(operation: string) {
        controller.installers.open_installers(targetService, targetAppId, targetGameId, targetGameName, operation)
    }

    Menu {
        id: gameMenu
        objectName: "libraryGameMenu"

        MenuItem {
            objectName: "toggleFavorite"
            icon.source: Theme.icon(actions.controller.favorite ? "favorite-filled" : "favorite")
            text: actions.controller.favorite ? qsTr("Remove from Favorites") : qsTr("Add to Favorites")
            enabled: actions.targetGameId.length > 0 && actions.controller.organizationReady
            onTriggered: actions.controller.set_favorite(actions.targetGameId, !actions.controller.favorite)
        }

        MenuItem {
            text: actions.controller.hidden ? qsTr("Unhide Game") : qsTr("Hide Game")
            icon.source: Theme.icon(actions.controller.hidden ? "visible" : "hidden")
            enabled: actions.targetGameId.length > 0 && actions.controller.organizationReady
            onTriggered: actions.controller.set_hidden(actions.targetGameId, !actions.controller.hidden)
        }

        MenuItem {
            objectName: "editGameCategories"
            icon.source: Theme.icon("category")
            text: qsTr("Edit Categories…")
            enabled: actions.targetGameId.length > 0
            onTriggered: categoryLoader.active = true
        }

        MenuSeparator {}

        MenuItem {
            objectName: "installGame"
            icon.source: Theme.icon("download")
            text: qsTr("Install…")
            visible: actions.targetCanInstall
            onTriggered: actions.openInstaller("install")
        }

        MenuItem {
            text: qsTr("Update or Repair…")
            icon.source: Theme.icon("refresh")
            visible: actions.targetCanUpdate
            onTriggered: actions.openInstaller("update")
        }

        MenuItem {
            text: qsTr("Install DLC…")
            icon.source: Theme.icon("package")
            visible: actions.targetCanInstallDlc
            onTriggered: actions.openInstaller("dlc")
        }

        MenuItem {
            objectName: "locateLocalGame"
            icon.source: Theme.icon("link")
            text: qsTr("Locate Installed Linux Game…")
            visible: actions.targetCanLinkLocalGame
            onTriggered: actions.controller.localGames.open_registration(actions.targetGameId, actions.targetGameName)
        }

        MenuItem {
            objectName: "configureGame"
            icon.source: Theme.icon("configure")
            text: qsTr("Configure…")
            enabled: actions.targetInstalled
            onTriggered: actions.controller.configuration.open_game(actions.targetGameId, actions.targetGameName)
        }

        MenuItem {
            text: qsTr("Play with Launch Options")
            icon.source: Theme.icon("play")
            enabled: actions.targetCanPlay
            onTriggered: actions.controller.launch(actions.targetGameId, true)
        }

        MenuItem {
            objectName: "showGameLogs"
            icon.source: Theme.icon("terminal")
            text: qsTr("Show Logs…")
            enabled: actions.targetInstalled
            onTriggered: {
                actions.controller.gameLog.open_log(actions.targetGameId)
                logLoader.active = true
            }
        }

        MenuItem {
            objectName: "manageGameShortcuts"
            icon.source: Theme.icon("external")
            text: qsTr("Manage Shortcuts…")
            enabled: actions.targetInstalled
            onTriggered: {
                actions.controller.gameShortcuts.open_shortcuts(actions.targetGameId)
                shortcutsLoader.active = true
            }
        }

        MenuItem {
            text: qsTr("Browse Files")
            icon.source: Theme.icon("folder")
            enabled: actions.targetInstalled
            onTriggered: actions.controller.browse_files(actions.targetGameId)
        }

        MenuSeparator {}

        MenuItem {
            objectName: "moveGame"
            icon.source: Theme.icon("folder")
            text: qsTr("Move Game…")
            enabled: actions.targetInstalled && actions.targetCanMaintain
            onTriggered: {
                actions.controller.gameMaintenance.open_maintenance(actions.targetGameId)
                moveLoader.active = true
            }
        }

        MenuItem {
            objectName: "uninstallGame"
            icon.source: Theme.icon("trash")
            text: actions.targetInstalled ? qsTr("Uninstall Game…") : qsTr("Remove from Library…")
            enabled: actions.targetCanMaintain
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
