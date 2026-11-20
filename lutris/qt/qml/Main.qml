pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

ApplicationWindow {
    id: window

    required property QtObject controller
    required property QtObject prompts

    title: qsTr("Lutris")
    width: 1200
    height: 760
    minimumWidth: 720
    minimumHeight: 460

    Binding {
        target: Theme
        property: "preference"
        value: window.controller.preferences.theme
    }

    LibraryView {
        anchors.fill: parent
        controller: window.controller
        onAddMenuRequested: button => addMenu.popup(button, 0, button.height + 4)
        onMainMenuRequested: button => mainMenu.popup(button, button.width - mainMenu.width, button.height + 4)
    }

    Menu {
        id: addMenu
        objectName: "addMenu"

        MenuItem {
            objectName: "addGame"
            text: qsTr("Add Game…")
            icon.source: Theme.icon("plus")
            onTriggered: window.controller.configuration.open_new_game()
        }

        MenuItem {
            objectName: "addLocalGame"
            text: qsTr("Add Locally Installed Game…")
            icon.source: Theme.icon("folder")
            onTriggered: window.controller.localGames.open_registration("", "")
        }

        MenuItem {
            text: qsTr("Run Windows Setup…")
            icon.source: Theme.icon("package")
            enabled: !window.controller.installers.installation.active
            onTriggered: windowsSetup.open()
        }

        MenuSeparator {}

        MenuItem {
            text: qsTr("Import ROMs…")
            icon.source: Theme.icon("download")
            enabled: !window.controller.gameImports.busy
            onTriggered: romFolder.open()
        }

        MenuItem {
            text: qsTr("Import from Playtron…")
            icon.source: Theme.icon("download")
            enabled: !window.controller.gameImports.busy
            onTriggered: {
                importDialog.scanningRoms = false
                window.controller.gameImports.import_playtron()
                importDialog.open()
            }
        }
    }

    Menu {
        id: mainMenu
        objectName: "mainMenu"

        MenuItem {
            objectName: "artworkSources"
            text: qsTr("Artwork Sources…")
            icon.source: Theme.icon("image")
            onTriggered: window.controller.artworkSettings.open_settings()
        }

        MenuSeparator {}

        MenuItem {
            objectName: "globalOptions"
            text: qsTr("Global Options…")
            icon.source: Theme.icon("configure")
            onTriggered: window.controller.configuration.open_system()
        }

        MenuItem {
            objectName: "openPreferences"
            text: qsTr("Preferences…")
            icon.source: Theme.icon("settings")
            onTriggered: window.controller.preferences.open_preferences()
        }

        MenuSeparator {}

        MenuItem {
            text: qsTr("Save Issue Report…")
            icon.source: Theme.icon("warning")
            onTriggered: window.controller.preferences.open_issue_report()
        }

        MenuItem {
            text: qsTr("Quit")
            icon.source: Theme.icon("power")
            onTriggered: Qt.quit()
        }
    }

    DropArea {
        anchors.fill: parent
        enabled: !window.controller.gameImports.busy && !importDialog.visible

        onEntered: drag => { drag.accepted = drag.hasUrls }
        onDropped: drop => {
            if (drop.hasUrls && window.controller.gameImports.import_rom_files(drop.urls)) {
                drop.acceptProposedAction()
                importDialog.scanningRoms = true
                importDialog.open()
            }
        }

        // Shows where ROMs dropped on the window go
        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            visible: parent.containsDrag
            radius: 16
            color: Theme.accentSubtle
            border.width: 2
            border.color: Theme.accent

            Label {
                anchors.centerIn: parent
                text: qsTr("Drop ROMs to import them")
                font.pointSize: Theme.titleSize
                font.weight: Font.DemiBold
                color: Theme.accentText
            }
        }
    }

    PromptHost { prompts: window.prompts }

    Shortcut {
        sequence: "Ctrl+Q"
        onActivated: Qt.quit()
    }

    Shortcut {
        sequence: "Ctrl+P"
        onActivated: window.controller.preferences.set_interface_option(
                         "hide_badges_on_icons", !window.controller.preferences.hideBadges)
    }

    Shortcut {
        sequences: [StandardKey.Preferences]
        onActivated: window.controller.preferences.open_preferences()
    }

    NativeDialogs.FolderDialog {
        id: romFolder
        title: qsTr("Select a folder containing ROMs")
        onAccepted: {
            importDialog.scanningRoms = true
            window.controller.gameImports.import_roms(selectedFolder)
            importDialog.open()
        }
    }

    ImportDialog {
        id: importDialog
        controller: window.controller.gameImports
    }

    IssueReportDialog { controller: window.controller.preferences }

    WindowsSetupDialog {
        id: windowsSetup
        controller: window.controller.installers
    }

    Connections {
        target: window.controller.storeSources
        function onLoginRequested() { storeLoginLoader.active = true }
        function onLoginClosed() {
            if (storeLoginLoader.status === Loader.Ready)
                (storeLoginLoader.item as StoreLoginDialog).close()
        }
    }

    Loader {
        id: storeLoginLoader
        active: false
        sourceComponent: StoreLoginDialog {
            controller: window.controller.storeSources
            onClosed: {
                controller.close_login()
                storeLoginLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as StoreLoginDialog).open()
    }

    Connections {
        target: window.controller.localGames
        function onRequested() { localGameLoader.active = true }
    }

    Loader {
        id: localGameLoader
        active: false
        sourceComponent: LocalGameDialog {
            controller: window.controller.localGames
            onClosed: localGameLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) (item as LocalGameDialog).open()
    }

    Connections {
        target: window.controller.installers
        function onRequested() { installerLoader.active = true }
    }

    Loader {
        id: installerLoader
        active: false
        sourceComponent: InstallerDialog {
            controller: window.controller.installers
            onClosed: {
                controller.close_installers()
                installerLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as InstallerDialog).open()
    }

    Connections {
        target: window.controller.preferences
        function onRequested() { preferencesLoader.active = true }
    }

    Loader {
        id: preferencesLoader
        active: false
        sourceComponent: PreferencesDialog {
            controller: window.controller.preferences
            library: window.controller
            onClosed: preferencesLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) (item as PreferencesDialog).open()
    }

    Connections {
        target: window.controller.artworkSettings
        function onRequested() { artworkLoader.active = true }
    }

    Loader {
        id: artworkLoader
        active: false
        sourceComponent: ArtworkSettingsDialog {
            controller: window.controller.artworkSettings
            onClosed: artworkLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) (item as ArtworkSettingsDialog).open()
    }

    Connections {
        target: window.controller.configuration
        function onRequested() { configLoader.active = true }
    }

    Loader {
        id: configLoader
        active: false
        sourceComponent: ConfigDialog {
            controller: window.controller.configuration
            onClosed: {
                controller.close()
                configLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as ConfigDialog).open()
    }
}
