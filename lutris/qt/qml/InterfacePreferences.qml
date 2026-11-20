import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: page

    required property QtObject controller
    contentWidth: availableWidth

    ColumnLayout {
        width: page.availableWidth

        RowLayout {
            Label {
                text: qsTr("Theme")
                Layout.fillWidth: true
            }

            ComboBox {
                model: [qsTr("System Default"), qsTr("Light"), qsTr("Dark")]
                readonly property var keys: ["default", "light", "dark"]
                currentIndex: Math.max(0, keys.indexOf(page.controller.theme))
                Accessible.name: qsTr("Theme")
                onActivated: index => page.controller.set_theme(keys[index])
            }
        }

        CheckBox {
            text: qsTr("Minimize Lutris while a game is running")
            checked: page.controller.minimizeOnLaunch
            onToggled: page.controller.set_interface_option("hide_client_on_game_start", checked)
        }

        CheckBox {
            text: qsTr("Hide game titles in the grid")
            checked: page.controller.hideGameTitles
            onToggled: page.controller.set_interface_option("hide_text_under_icons", checked)
        }

        CheckBox {
            text: qsTr("Hide grid badges (Ctrl+P)")
            checked: page.controller.hideBadges
            onToggled: page.controller.set_interface_option("hide_badges_on_icons", checked)
        }

        CheckBox {
            text: qsTr("Show tray icon and keep Lutris open when the window closes")
            enabled: page.controller.trayAvailable
            checked: page.controller.trayEnabled
            onToggled: page.controller.set_interface_option("show_tray_icon", checked)
        }

        Label {
            visible: !page.controller.trayAvailable
            Layout.fillWidth: true
            text: qsTr("The desktop does not provide a system tray.")
            wrapMode: Text.WordWrap
        }

        CheckBox {
            text: qsTr("Enable Discord Rich Presence for available games")
            checked: page.controller.discordPresence
            onToggled: page.controller.set_interface_option("discord_rpc", checked)
        }
    }
}
