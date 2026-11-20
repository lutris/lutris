pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

Dialog {
    id: dialog
    objectName: "preferencesDialog"

    required property QtObject controller
    required property QtObject library

    readonly property QtObject runtime: library.runtimeUpdates
    readonly property var storage: controller.storage
    readonly property var pageList: [
        { title: qsTr("Sources"), icon: "store" },
        { title: qsTr("Storage"), icon: "storage" },
        { title: qsTr("Updates"), icon: "refresh" },
        { title: qsTr("Accounts"), icon: "user" },
        { title: qsTr("System"), icon: "info" },
        { title: qsTr("Options"), icon: "configure" },
        { title: qsTr("Runners"), icon: "runner" },
        { title: qsTr("Interface"), icon: "layout" }
    ]

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(960, parent.width - 48)
    height: Math.min(680, parent.height - 48)
    title: qsTr("Preferences")
    modal: true
    padding: 0
    topPadding: 0
    bottomPadding: 0
    header: null
    footer: null

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

    // A page's scrolling column, under the page's title
    component Page: ScrollView {
        id: page

        default property alias content: column.data

        contentWidth: availableWidth
        rightPadding: 8

        ColumnLayout {
            id: column
            width: page.availableWidth
            spacing: 22
        }
    }

    contentItem: RowLayout {
        spacing: 0

        Rectangle {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            topLeftRadius: 14
            bottomLeftRadius: 14
            color: Theme.sidebar

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: Theme.border
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                anchors.topMargin: 20
                spacing: 12

                Label {
                    Layout.leftMargin: 8
                    text: dialog.title
                    font.pointSize: Theme.titleSize
                    font.weight: Font.Bold
                }

                ListView {
                    id: pages
                    objectName: "preferencesPages"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: dialog.pageList
                    currentIndex: 0
                    spacing: 1
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: ItemDelegate {
                        required property var modelData
                        required property int index

                        width: ListView.view.width
                        text: modelData.title
                        icon.source: Theme.icon(modelData.icon)
                        highlighted: ListView.isCurrentItem
                        font.weight: highlighted ? Font.DemiBold : Font.Normal
                        onClicked: pages.currentIndex = index
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 28
                Layout.rightMargin: 12
                Layout.topMargin: 12
                Layout.bottomMargin: 8

                Label {
                    Layout.fillWidth: true
                    text: dialog.pageList[pages.currentIndex]?.title ?? ""
                    font.pointSize: Theme.headingSize * 0.8
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }

                ToolButton {
                    icon.source: Theme.icon("close")
                    Accessible.name: qsTr("Close")
                    onClicked: dialog.close()
                }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 28
                Layout.rightMargin: 20
                Layout.bottomMargin: 20
                currentIndex: pages.currentIndex

                // Sources
                Page {
                    SettingsGroup {
                        description: qsTr("Access your game libraries from these sources. A source that's turned off isn't listed in the sidebar.")

                        Repeater {
                            model: dialog.controller.sources

                            SettingsRow {
                                id: source

                                required property var modelData

                                title: modelData.name
                                subtitle: modelData.description

                                Switch {
                                    objectName: "sourceSwitch_" + source.modelData.id
                                    checked: source.modelData.enabled
                                    Accessible.name: qsTr("Use %1").arg(source.modelData.name)
                                    onToggled: dialog.controller.set_source_enabled(source.modelData.id, checked)
                                }

                                details: CheckBox {
                                    visible: source.modelData.enabled
                                    checked: source.modelData.inGamesView
                                    text: qsTr("Show games from this source in the Games view")
                                    font.pointSize: Theme.smallSize
                                    onToggled: dialog.controller.set_source_in_games_view(source.modelData.id, checked)
                                }
                            }
                        }
                    }
                }

                // Storage
                Page {
                    SettingsGroup {
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

                            SettingsRow {
                                id: pathSetting

                                required property var modelData

                                title: modelData.title
                                subtitle: modelData.help

                                details: [
                                    RowLayout {
                                        Layout.fillWidth: true

                                        TextField {
                                            objectName: "storagePath_" + pathSetting.modelData.setting
                                            Layout.fillWidth: true
                                            text: pathSetting.modelData.path
                                            placeholderText: qsTr("Not set")
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
                                            icon.source: Theme.icon("folder")
                                            Accessible.name: qsTr("Browse for the %1 folder").arg(pathSetting.modelData.title)
                                            onClicked: {
                                                folderPicker.setting = pathSetting.modelData.setting
                                                folderPicker.open()
                                            }
                                        }
                                    },
                                    Label {
                                        Layout.fillWidth: true
                                        visible: text.length > 0
                                        text: pathSetting.modelData.message
                                        textFormat: Text.PlainText
                                        wrapMode: Text.WordWrap
                                        font.pointSize: Theme.smallSize
                                        color: pathSetting.modelData.error ? Theme.danger : Theme.warning
                                    }
                                ]
                            }
                        }
                    }
                }

                // Updates
                Page {
                    SettingsGroup {
                        title: qsTr("Components")
                        description: qsTr("Lutris downloads umu, gogdl, Winetricks and the other tools that games are installed and run with.")

                        SettingsRow {
                            title: qsTr("Update components automatically")

                            Switch {
                                objectName: "autoUpdateRuntime"
                                checked: dialog.runtime.autoUpdate
                                Accessible.name: qsTr("Update components automatically")
                                onToggled: dialog.runtime.set_auto_update(checked)
                            }
                        }

                        SettingsRow {
                            title: qsTr("Check for updates")
                            subtitle: dialog.runtime.statusText

                            BusyIndicator {
                                implicitWidth: 26
                                implicitHeight: 26
                                padding: 0
                                visible: running
                                running: dialog.runtime.running
                            }

                            Button {
                                objectName: "checkRuntimeUpdates"
                                text: qsTr("Check for Updates")
                                icon.source: Theme.icon("refresh")
                                enabled: !dialog.runtime.running
                                onClicked: dialog.runtime.check()
                            }
                        }
                    }

                    SettingsGroup {
                        title: qsTr("Artwork")

                        SettingsRow {
                            title: qsTr("Artwork sources")
                            subtitle: qsTr("Choose where artwork comes from, such as SteamGridDB.")

                            Button {
                                text: qsTr("Artwork Sources…")
                                onClicked: dialog.library.artworkSettings.open_settings()
                            }
                        }
                    }
                }

                // Accounts
                Page {
                    SettingsGroup {
                        title: qsTr("Steam account")
                        description: qsTr("Select which Steam account is used for Steam integration and Steam shortcuts.")

                        ButtonGroup { id: accounts }

                        Repeater {
                            model: dialog.controller.steamAccounts

                            SettingsRow {
                                id: account

                                required property var modelData

                                title: modelData.name

                                RadioButton {
                                    Accessible.name: account.modelData.name
                                    checked: account.modelData.active
                                    ButtonGroup.group: accounts
                                    onToggled: if (checked) dialog.controller.set_steam_account(account.modelData.id)
                                }
                            }
                        }

                        SettingsRow {
                            visible: dialog.controller.steamAccounts.length === 0
                            title: qsTr("No Steam account found")
                            subtitle: qsTr("Sign in to Steam on this computer to use its account here.")
                        }
                    }
                }

                // System
                Page {
                    RowLayout {
                        Layout.fillWidth: true

                        Button {
                            text: qsTr("Copy System Info")
                            icon.source: Theme.icon("info")
                            onClicked: dialog.controller.copy_system_info()
                        }

                        Button {
                            text: qsTr("Copy Lutris Log")
                            icon.source: Theme.icon("terminal")
                            onClicked: dialog.controller.copy_log()
                        }
                    }

                    Repeater {
                        model: dialog.controller.systemInfo

                        SettingsGroup {
                            id: section

                            required property var modelData

                            title: modelData.title

                            Repeater {
                                model: section.modelData.items

                                SettingsRow {
                                    id: item

                                    required property var modelData

                                    topPadding: 8
                                    bottomPadding: 8

                                    details: RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 16

                                        Label {
                                            Layout.preferredWidth: 220
                                            Layout.alignment: Qt.AlignTop
                                            text: item.modelData.name
                                            textFormat: Text.PlainText
                                            color: Theme.textMuted
                                            wrapMode: Text.Wrap
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            text: item.modelData.value
                                            textFormat: Text.PlainText
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Options
                Page {
                    SettingsGroup {
                        SettingsRow {
                            title: qsTr("Global options")
                            subtitle: qsTr("Global options are the system options every runner and game starts from.")

                            Button {
                                text: qsTr("Edit Global Options…")
                                icon.source: Theme.icon("configure")
                                onClicked: dialog.library.configuration.open_system()
                            }
                        }
                    }
                }

                Loader {
                    active: visible
                    sourceComponent: RunnerPreferences {
                        controller: dialog.library.runnerManager
                        configuration: dialog.library.configuration
                    }
                }

                InterfacePreferences { controller: dialog.controller }
            }
        }
    }
}
