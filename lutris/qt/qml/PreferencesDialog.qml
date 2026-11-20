pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "preferencesDialog"

    required property QtObject controller
    required property QtObject library

    readonly property QtObject runtime: library.runtimeUpdates
    readonly property var storage: controller.storage

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(900, parent.width - 32)
    height: Math.min(640, parent.height - 32)
    title: qsTr("Preferences")
    modal: true
    standardButtons: Dialog.Close

    NativeDialogs.FolderDialog {
        id: folderPicker

        property string setting: ""

        title: qsTr("Select folder")
        onAccepted: {
            const path = dialog.controller.local_path(selectedFolder)
            if (setting === "game")
                dialog.controller.set_game_path(path)
            else if (setting === "cache")
                dialog.controller.set_cache_path(path)
            else
                dialog.controller.set_bios_path(path)
        }
    }

    contentItem: RowLayout {
        spacing: 12

        ListView {
            id: pages
            objectName: "preferencesPages"
            Layout.preferredWidth: 180
            Layout.fillHeight: true
            model: [qsTr("Sources"), qsTr("Storage"), qsTr("Updates"), qsTr("Accounts"), qsTr("System"), qsTr("Options"), qsTr("Runners")]
            currentIndex: 0

            delegate: ItemDelegate {
                required property string modelData
                required property int index

                width: ListView.view.width
                text: modelData
                highlighted: ListView.isCurrentItem
                onClicked: pages.currentIndex = index
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: pages.currentIndex

            // Sources
            ScrollView {
                id: sourcesView
                contentWidth: availableWidth

                ColumnLayout {
                    width: sourcesView.availableWidth
                    spacing: 8

                    Label {
                        Layout.fillWidth: true
                        text: qsTr("Access your game libraries from these sources. A source that's turned off isn't listed in the sidebar.")
                        wrapMode: Text.WordWrap
                    }

                    Repeater {
                        model: dialog.controller.sources

                        RowLayout {
                            id: source

                            required property var modelData

                            Layout.preferredWidth: sourcesView.availableWidth
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2

                                Label {
                                    Layout.fillWidth: true
                                    text: source.modelData.name
                                    font.bold: true
                                }

                                Label {
                                    Layout.fillWidth: true
                                    visible: text.length > 0
                                    text: source.modelData.description
                                    wrapMode: Text.WordWrap
                                }

                                CheckBox {
                                    visible: source.modelData.enabled
                                    checked: source.modelData.inGamesView
                                    text: qsTr("Show games from this source in the Games view")
                                    onToggled: dialog.controller.set_source_in_games_view(source.modelData.id, checked)
                                }
                            }

                            Switch {
                                objectName: "sourceSwitch_" + source.modelData.id
                                checked: source.modelData.enabled
                                Accessible.name: qsTr("Use %1").arg(source.modelData.name)
                                onToggled: dialog.controller.set_source_enabled(source.modelData.id, checked)
                            }
                        }
                    }
                }
            }

            // Storage
            ColumnLayout {
                spacing: 8

                Repeater {
                    model: [
                        { setting: "game", title: qsTr("Game library"), path: dialog.storage.gamePath ?? "",
                          help: qsTr("The default folder where you install your games."),
                          message: "", error: false },
                        { setting: "cache", title: qsTr("Installer cache"), path: dialog.storage.cachePath ?? "",
                          help: qsTr("If set, files downloaded during game installs are kept there. Otherwise they're discarded."),
                          message: dialog.storage.cacheMessage ?? "", error: !(dialog.storage.cacheValid ?? true) },
                        { setting: "bios", title: qsTr("Emulator BIOS files location"), path: dialog.storage.biosPath ?? "",
                          help: qsTr("The folder Lutris searches for emulator BIOS files."),
                          message: dialog.storage.biosWarning ?? "", error: false }
                    ]

                    ColumnLayout {
                        id: pathSetting

                        required property var modelData

                        Layout.fillWidth: true
                        spacing: 4

                        Label {
                            text: pathSetting.modelData.title
                            font.bold: true
                        }

                        RowLayout {
                            Layout.fillWidth: true

                            TextField {
                                objectName: "storagePath_" + pathSetting.modelData.setting
                                Layout.fillWidth: true
                                text: pathSetting.modelData.path
                                Accessible.name: pathSetting.modelData.title
                                onEditingFinished: {
                                    if (text === pathSetting.modelData.path)
                                        return
                                    if (pathSetting.modelData.setting === "game")
                                        dialog.controller.set_game_path(text)
                                    else if (pathSetting.modelData.setting === "cache")
                                        dialog.controller.set_cache_path(text)
                                    else
                                        dialog.controller.set_bios_path(text)
                                }
                            }

                            Button {
                                text: qsTr("Browse…")
                                Accessible.name: qsTr("Browse for the %1 folder").arg(pathSetting.modelData.title)
                                onClicked: {
                                    folderPicker.setting = pathSetting.modelData.setting
                                    folderPicker.open()
                                }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            text: pathSetting.modelData.help
                            wrapMode: Text.WordWrap
                            font.italic: true
                        }

                        Label {
                            Layout.fillWidth: true
                            visible: text.length > 0
                            text: pathSetting.modelData.message
                            textFormat: Text.PlainText
                            wrapMode: Text.WordWrap
                            color: pathSetting.modelData.error ? "firebrick" : "darkorange"
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }

            // Updates
            ColumnLayout {
                spacing: 8

                Label {
                    text: qsTr("Runtime")
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: qsTr("The runtime includes umu and the other components games run with.")
                    wrapMode: Text.WordWrap
                }

                CheckBox {
                    objectName: "autoUpdateRuntime"
                    checked: dialog.runtime.autoUpdate
                    text: qsTr("Update the runtime automatically")
                    onToggled: dialog.runtime.set_auto_update(checked)
                }

                RowLayout {
                    Button {
                        objectName: "checkRuntimeUpdates"
                        text: qsTr("Check for Updates")
                        enabled: !dialog.runtime.running
                        onClicked: dialog.runtime.check()
                    }

                    Label {
                        Layout.fillWidth: true
                        text: dialog.runtime.statusText
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                    }
                }

                Label {
                    Layout.topMargin: 12
                    text: qsTr("Artwork")
                    font.bold: true
                }

                RowLayout {
                    Button {
                        text: qsTr("Download Missing Artwork")
                        enabled: !dialog.library.updatingArtwork
                        onClicked: dialog.library.update_artwork()
                    }

                    Button {
                        text: qsTr("Artwork Sources…")
                        onClicked: dialog.library.artworkSettings.open_settings()
                    }
                }

                Item { Layout.fillHeight: true }
            }

            // Accounts
            ColumnLayout {
                spacing: 8

                Label {
                    text: qsTr("Steam account")
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Select which Steam account is used for Steam integration and Steam shortcuts.")
                    wrapMode: Text.WordWrap
                }

                ButtonGroup { id: accounts }

                Repeater {
                    model: dialog.controller.steamAccounts

                    RadioButton {
                        required property var modelData

                        text: modelData.name
                        checked: modelData.active
                        ButtonGroup.group: accounts
                        onToggled: if (checked) dialog.controller.set_steam_account(modelData.id)
                    }
                }

                Label {
                    visible: dialog.controller.steamAccounts.length === 0
                    text: qsTr("No Steam account found")
                }

                Item { Layout.fillHeight: true }
            }

            // System
            ColumnLayout {
                spacing: 8

                RowLayout {
                    Button {
                        text: qsTr("Copy System Info")
                        onClicked: dialog.controller.copy_system_info()
                    }

                    Button {
                        text: qsTr("Copy Lutris Log")
                        onClicked: dialog.controller.copy_log()
                    }
                }

                ScrollView {
                    id: systemView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentWidth: availableWidth

                    ColumnLayout {
                        width: systemView.availableWidth

                        Repeater {
                            model: dialog.controller.systemInfo

                            ColumnLayout {
                                id: section

                                required property var modelData

                                Layout.fillWidth: true

                                Label {
                                    Layout.topMargin: 8
                                    text: section.modelData.title
                                    font.bold: true
                                }

                                Repeater {
                                    model: section.modelData.items

                                    RowLayout {
                                        required property var modelData

                                        Layout.fillWidth: true

                                        Label {
                                            Layout.preferredWidth: 220
                                            text: parent.modelData.name
                                            textFormat: Text.PlainText
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            text: parent.modelData.value
                                            textFormat: Text.PlainText
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Options
            ColumnLayout {
                spacing: 8

                Label {
                    Layout.fillWidth: true
                    text: qsTr("Global options are the system options every runner and game starts from.")
                    wrapMode: Text.WordWrap
                }

                Button {
                    text: qsTr("Edit Global Options…")
                    onClicked: dialog.library.configuration.open_system()
                }

                Item { Layout.fillHeight: true }
            }

            Loader {
                active: visible
                sourceComponent: RunnerPreferences {
                    controller: dialog.library.runnerManager
                    configuration: dialog.library.configuration
                }
            }
        }
    }
}
