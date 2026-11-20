pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import LutrisStyle

// The selected game, with its details and the buttons to play or install it
Rectangle {
    id: bar

    required property QtObject controller
    // The selected game's card or row, which carries its details
    required property Item game

    readonly property bool active: controller.selectedRow >= 0
    readonly property string details: {
        if (!game)
            return ""
        const parts = [game.runnerText, game.platformText].filter(part => part.length > 0)
        if (game.playTimeText.length > 0)
            parts.push(qsTr("%1 played").arg(game.playTimeText))
        if (game.lastPlayedText.length > 0)
            parts.push(qsTr("Last played %1").arg(game.lastPlayedText))
        return parts.join("  ·  ")
    }

    function showActions(atPointer: bool): void {
        actions.showMenu(atPointer)
    }

    implicitHeight: 76
    visible: controller.gameCount > 0
    color: Theme.sidebar

    Rectangle {
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 16
        spacing: 14

        Item {
            implicitWidth: 44
            implicitHeight: 44

            Rectangle {
                anchors.fill: parent
                radius: Theme.radius
                color: Theme.surface
                border.color: Theme.border
                visible: !cover.visible
            }

            ArtworkImage {
                id: cover
                anchors.fill: parent
                radius: Theme.radius
                source: bar.game ? (bar.game.iconUrl.toString().length > 0 ? bar.game.iconUrl : bar.game.coverUrl) : ""
                visible: status === Image.Ready
            }

            IconImage {
                anchors.centerIn: parent
                width: 28
                height: 28
                visible: !cover.visible
                name: bar.game?.iconName ?? ""
                source: bar.controller.placeholderArtwork
                sourceSize: Qt.size(56, 56)
                color: "transparent"
                Accessible.ignored: true
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Label {
                Layout.fillWidth: true
                text: bar.active ? bar.controller.selectedGameName : qsTr("No game selected")
                color: bar.active ? Theme.text : Theme.textMuted
                textFormat: Text.PlainText
                font.pointSize: Theme.largeSize
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    visible: bar.controller.canStop
                    implicitWidth: running.implicitWidth + 16
                    implicitHeight: running.implicitHeight + 2
                    radius: height / 2
                    color: Qt.alpha(Theme.success, 0.16)

                    Label {
                        id: running
                        anchors.centerIn: parent
                        text: qsTr("Running")
                        font.pointSize: Theme.smallSize * 0.9
                        font.weight: Font.DemiBold
                        color: Theme.success
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: bar.active ? bar.details : qsTr("Choose a game to play, install or manage it")
                    textFormat: Text.PlainText
                    font.pointSize: Theme.smallSize
                    color: Theme.textMuted
                    elide: Text.ElideRight
                }
            }
        }

        Button {
            objectName: "stopGame"
            visible: bar.controller.canStop
            highlighted: true
            text: qsTr("Stop")
            icon.source: Theme.icon("stop")
            // Drawn like a destructive dialog button
            DialogButtonBox.buttonRole: DialogButtonBox.DestructiveRole
            onClicked: bar.controller.stop()
        }

        Button {
            objectName: "playGame"
            visible: !bar.controller.canStop && (bar.controller.canPlay || !bar.controller.canInstall)
            enabled: bar.controller.canPlay
            highlighted: true
            Layout.preferredWidth: Math.max(implicitWidth, 112)
            text: qsTr("Play")
            icon.source: Theme.icon("play")
            onClicked: bar.controller.play()
        }

        Button {
            objectName: "installSelectedGame"
            visible: !bar.controller.canStop && !bar.controller.canPlay && bar.controller.canInstall
            highlighted: true
            Layout.preferredWidth: Math.max(implicitWidth, 112)
            text: qsTr("Install")
            icon.source: Theme.icon("download")
            onClicked: bar.controller.installers.open_installers(
                           bar.controller.selectedGameService, bar.controller.selectedGameAppId,
                           bar.controller.selectedGameId, bar.controller.selectedGameName, "install")
        }

        GameActions {
            id: actions
            controller: bar.controller
        }
    }
}
