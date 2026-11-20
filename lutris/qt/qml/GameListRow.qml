pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import LutrisStyle

ItemDelegate {
    id: row

    required property int index
    required property string gameTitle
    required property string runnerText
    required property string platformText
    required property string yearText
    required property string lastPlayedText
    required property string installedAtText
    required property string playTimeText
    required property bool installed
    required property bool running
    required property url coverUrl
    required property url bannerUrl
    required property url iconUrl
    required property string iconName
    required property var columns
    required property url placeholder
    required property bool selected
    required property bool keyboardFocus

    readonly property string gameStatus: running ? qsTr("Running") : installed ? "" : qsTr("Not installed")

    signal menuRequested()

    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    padding: 6
    horizontalPadding: 12
    Accessible.name: gameTitle
    Accessible.description: gameStatus

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: row.menuRequested()
    }

    background: Rectangle {
        radius: Theme.radius
        color: row.selected ? Theme.accentSubtle : row.down ? Theme.pressed : row.hovered ? Theme.hover : "transparent"
        border.width: row.keyboardFocus ? 1 : 0
        border.color: Theme.accent
    }

    contentItem: RowLayout {
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 180
            spacing: 10

            Item {
                implicitWidth: 28
                implicitHeight: 28

                ArtworkImage {
                    id: icon
                    anchors.fill: parent
                    radius: Theme.radiusSmall
                    fillMode: Image.PreserveAspectFit
                    source: row.iconUrl
                    visible: status === Image.Ready
                }

                IconImage {
                    anchors.fill: parent
                    visible: !icon.visible
                    name: row.iconName
                    source: row.placeholder
                    sourceSize: Qt.size(56, 56)
                    color: "transparent"
                    opacity: 0.8
                    Accessible.ignored: true
                }
            }

            Label {
                Layout.fillWidth: true
                text: row.gameTitle
                textFormat: Text.PlainText
                font.weight: row.selected || row.running ? Font.DemiBold : Font.Normal
                color: row.installed || row.running ? Theme.text : Theme.textMuted
                elide: Text.ElideRight
            }

            Rectangle {
                visible: row.gameStatus.length > 0
                implicitWidth: statusLabel.implicitWidth + 14
                implicitHeight: statusLabel.implicitHeight + 4
                radius: height / 2
                color: row.running ? Qt.alpha(Theme.success, 0.16) : Theme.hover

                Label {
                    id: statusLabel
                    anchors.centerIn: parent
                    text: row.gameStatus
                    font.pointSize: Theme.smallSize * 0.9
                    font.weight: Font.Medium
                    color: row.running ? Theme.success : Theme.textMuted
                }
            }
        }

        Repeater {
            model: row.columns.length
            delegate: Label {
                required property int index
                readonly property var column: row.columns[index]

                Layout.minimumWidth: column.width
                Layout.preferredWidth: column.width
                Layout.maximumWidth: column.width
                visible: column.visible
                text: [row.runnerText, row.platformText, row.yearText, row.lastPlayedText,
                       row.installedAtText, row.playTimeText][index]
                textFormat: Text.PlainText
                color: Theme.textMuted
                elide: Text.ElideRight
            }
        }
    }
}
