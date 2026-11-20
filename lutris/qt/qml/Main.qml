pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window

    required property QtObject controller
    required property QtObject prompts

    title: qsTr("Lutris")
    width: 1100
    height: 700
    minimumWidth: 640
    minimumHeight: 420

    menuBar: MenuBar {
        Menu {
            title: qsTr("Library")

            MenuItem {
                objectName: "addGame"
                text: qsTr("Add Game…")
                onTriggered: window.controller.configuration.open_new_game()
            }

            MenuItem {
                objectName: "addLocalGame"
                text: qsTr("Add Locally Installed Game…")
                onTriggered: window.controller.localGames.open_registration("", "")
            }

            MenuItem {
                text: qsTr("Run Windows Setup…")
                enabled: !window.controller.installers.installation.active
                onTriggered: windowsSetup.open()
            }

            MenuSeparator {}

            MenuItem {
                objectName: "globalOptions"
                text: qsTr("Global Options…")
                onTriggered: window.controller.configuration.open_system()
            }

            MenuItem {
                objectName: "openPreferences"
                text: qsTr("Preferences…")
                onTriggered: window.controller.preferences.open_preferences()
            }
        }
    }

    header: LibraryToolbar { controller: window.controller }

    LibraryView {
        anchors.fill: parent
        controller: window.controller
    }

    PromptHost { prompts: window.prompts }

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

    footer: ToolBar {
        id: statusBar

        // A running runtime update takes over the status bar until it's done
        readonly property string message: window.controller.runtimeUpdates.running
                                          ? window.controller.runtimeUpdates.statusText
                                          : window.controller.statusText

        visible: message.length > 0
        implicitHeight: visible ? statusLabel.implicitHeight + 14 : 0

        Label {
            id: statusLabel
            objectName: "libraryStatus"
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 12
            text: statusBar.message
            Accessible.role: Accessible.StatusBar
        }
    }
}
