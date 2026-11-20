pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

ScrollView {
    id: page

    required property QtObject controller
    contentWidth: availableWidth
    rightPadding: 8

    ColumnLayout {
        width: page.availableWidth
        spacing: 22

        SettingsGroup {
            title: qsTr("Appearance")

            SettingsRow {
                title: qsTr("Theme")

                // The themes, as a segmented control
                Rectangle {
                    implicitWidth: themes.implicitWidth + 6
                    implicitHeight: themes.implicitHeight + 6
                    radius: Theme.radius
                    color: Theme.dark ? Theme.field : Theme.controlPressed
                    border.color: Theme.border

                    Row {
                        id: themes
                        anchors.centerIn: parent
                        spacing: 2

                        Repeater {
                            model: [
                                { key: "default", title: qsTr("System Default") },
                                { key: "light", title: qsTr("Light") },
                                { key: "dark", title: qsTr("Dark") }
                            ]
                            delegate: AbstractButton {
                                id: choice

                                required property var modelData
                                readonly property bool current: page.controller.theme === modelData.key

                                implicitWidth: label.implicitWidth + 24
                                implicitHeight: 28
                                hoverEnabled: true
                                text: modelData.title
                                checkable: true
                                checked: current
                                Accessible.role: Accessible.RadioButton
                                onClicked: page.controller.set_theme(modelData.key)

                                contentItem: Label {
                                    id: label
                                    text: choice.text
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    font.weight: choice.current ? Font.DemiBold : Font.Normal
                                    color: choice.current || choice.hovered ? Theme.text : Theme.textMuted
                                }

                                background: Rectangle {
                                    radius: Theme.radiusSmall
                                    color: choice.current ? Theme.raised : choice.hovered ? Theme.hover : "transparent"
                                    border.color: choice.current ? Theme.borderStrong : "transparent"
                                }
                            }
                        }
                    }
                }
            }

            SettingsRow {
                title: qsTr("Hide game titles in the grid")

                Switch {
                    checked: page.controller.hideGameTitles
                    Accessible.name: qsTr("Hide game titles in the grid")
                    onToggled: page.controller.set_interface_option("hide_text_under_icons", checked)
                }
            }

            SettingsRow {
                title: qsTr("Hide grid badges")
                subtitle: qsTr("Toggle them at any time with Ctrl+P.")

                Switch {
                    checked: page.controller.hideBadges
                    Accessible.name: qsTr("Hide grid badges")
                    onToggled: page.controller.set_interface_option("hide_badges_on_icons", checked)
                }
            }
        }

        SettingsGroup {
            title: qsTr("Behavior")

            SettingsRow {
                title: qsTr("Minimize Lutris while a game is running")

                Switch {
                    checked: page.controller.minimizeOnLaunch
                    Accessible.name: qsTr("Minimize Lutris while a game is running")
                    onToggled: page.controller.set_interface_option("hide_client_on_game_start", checked)
                }
            }

            SettingsRow {
                title: qsTr("Show tray icon and keep Lutris open when the window closes")
                subtitle: page.controller.trayAvailable ? "" : qsTr("The desktop does not provide a system tray.")

                Switch {
                    enabled: page.controller.trayAvailable
                    checked: page.controller.trayEnabled
                    Accessible.name: qsTr("Show tray icon")
                    onToggled: page.controller.set_interface_option("show_tray_icon", checked)
                }
            }

            SettingsRow {
                title: qsTr("Enable Discord Rich Presence for available games")

                Switch {
                    checked: page.controller.discordPresence
                    Accessible.name: qsTr("Enable Discord Rich Presence")
                    onToggled: page.controller.set_interface_option("discord_rpc", checked)
                }
            }
        }
    }
}
