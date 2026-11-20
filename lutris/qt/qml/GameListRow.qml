import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

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
    required property bool showPlatform
    required property bool showDetails
    required property bool selected
    required property bool keyboardFocus

    readonly property string gameStatus: running ? qsTr("Running") : installed ? "" : qsTr("Not installed")

    focusPolicy: Qt.NoFocus
    padding: 7
    Accessible.name: gameTitle
    Accessible.description: gameStatus

    background: Rectangle {
        color: row.selected ? row.palette.highlight : row.index % 2 ? row.palette.alternateBase : row.palette.base
        border.width: row.keyboardFocus ? 2 : 0
        border.color: row.palette.highlightedText
    }

    contentItem: RowLayout {
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Label {
                Layout.fillWidth: true
                text: row.gameTitle
                textFormat: Text.PlainText
                font.bold: row.running
                elide: Text.ElideRight
                color: row.selected ? row.palette.highlightedText : row.palette.text
            }

            Label {
                visible: row.gameStatus.length > 0
                text: row.gameStatus
                color: row.selected ? row.palette.highlightedText : row.palette.text
            }
        }

        Repeater {
            model: [
                { text: row.runnerText, width: 88, visible: row.showPlatform },
                { text: row.platformText, width: 88, visible: row.showPlatform },
                { text: row.yearText, width: 58, visible: row.showDetails },
                { text: row.lastPlayedText, width: 100, visible: row.showDetails },
                { text: row.installedAtText, width: 100, visible: row.showDetails },
                { text: row.playTimeText, width: 105, visible: row.showDetails }
            ]
            delegate: Label {
                required property var modelData
                Layout.minimumWidth: modelData.width
                Layout.preferredWidth: modelData.width
                Layout.maximumWidth: modelData.width
                visible: modelData.visible
                text: modelData.text
                textFormat: Text.PlainText
                color: row.selected ? row.palette.highlightedText : row.palette.text
                elide: Text.ElideRight
            }
        }
    }
}
