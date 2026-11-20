pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

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

            MenuItem {
                text: qsTr("Import ROMs…")
                enabled: !window.controller.gameImports.busy
                onTriggered: romFolder.open()
            }

            MenuItem {
                text: qsTr("Import from Playtron…")
                enabled: !window.controller.gameImports.busy
                onTriggered: {
                    importDialog.scanningRoms = false
                    window.controller.gameImports.import_playtron()
                    importDialog.open()
                }
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

            MenuSeparator {}

            MenuItem {
                text: qsTr("Quit")
                onTriggered: Qt.quit()
            }
        }

        Menu {
            title: qsTr("Help")
            MenuItem {
                text: qsTr("Save Issue Report…")
                onTriggered: window.controller.preferences.open_issue_report()
            }
        }
    }

    header: LibraryToolbar { controller: window.controller }

    LibraryView {
        anchors.fill: parent
        controller: window.controller
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

    footer: ToolBar {
        id: statusBar

        // A running runtime update takes over the status bar until it's done
        readonly property string message: window.controller.runtimeUpdates.running
                                          ? window.controller.runtimeUpdates.statusText
                                          : window.controller.statusText

        visible: message.length > 0 || window.controller.cloudSaves.transfers.length > 0
        implicitHeight: visible ? statusRows.implicitHeight + 14 : 0

        ColumnLayout {
            id: statusRows
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12

            Repeater {
                model: window.controller.cloudSaves.transfers
                delegate: RowLayout {
                    id: transfer
                    required property var modelData
                    Layout.fillWidth: true

                    Label {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: transfer.modelData.label
                        textFormat: Text.PlainText
                    }
                    ProgressBar {
                        value: transfer.modelData.progress
                        indeterminate: value === 0 && transfer.modelData.canSkip
                    }
                    Button {
                        text: qsTr("Skip Cloud Sync")
                        enabled: transfer.modelData.canSkip
                        onClicked: window.controller.cloudSaves.skip(transfer.modelData.id)
                    }
                }
            }

            Label {
                objectName: "libraryStatus"
                Layout.fillWidth: true
                visible: text.length > 0
                text: statusBar.message
                textFormat: Text.PlainText
                Accessible.role: Accessible.StatusBar
            }
        }
    }
}
