import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ItemDelegate {
    id: card

    required property int index
    required property string gameTitle
    required property bool installed
    required property bool running
    required property url coverUrl
    required property url bannerUrl
    required property url iconUrl
    required property string iconName
    required property bool banners
    required property bool selected
    required property bool keyboardFocus
    required property url placeholder

    readonly property string gameStatus: running ? qsTr("Running") : installed ? "" : qsTr("Not installed")
    readonly property url primaryArtwork: banners ? bannerUrl : coverUrl
    readonly property url alternateArtwork: banners ? coverUrl : bannerUrl
    readonly property color cardText: selected ? palette.highlightedText : palette.text

    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    padding: 12
    Accessible.name: gameTitle
    Accessible.description: gameStatus
    ToolTip.visible: hovered && titleLabel.truncated
    ToolTip.text: gameTitle

    background: Rectangle {
        anchors.fill: parent
        anchors.margins: 5
        radius: 8
        color: card.selected ? card.palette.highlight : card.palette.alternateBase
        border.width: card.keyboardFocus ? 2 : card.hovered ? 1 : 0
        border.color: card.selected ? card.palette.highlightedText : card.palette.highlight
    }

    contentItem: ColumnLayout {
        spacing: 3

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ArtworkImage {
                id: primary
                anchors.fill: parent
                source: card.primaryArtwork
                visible: status === Image.Ready
            }

            ArtworkImage {
                id: alternate
                anchors.fill: parent
                source: primary.status === Image.Null || primary.status === Image.Error ? card.alternateArtwork : ""
                visible: status === Image.Ready
            }

            ArtworkImage {
                id: localIcon
                anchors.centerIn: parent
                width: 48
                height: 48
                source: primary.visible || alternate.visible ? "" : card.iconUrl
                visible: status === Image.Ready
            }

            ToolButton {
                id: themedIcon
                anchors.centerIn: parent
                visible: !primary.visible && !alternate.visible && !localIcon.visible && card.iconName.length > 0
                enabled: false
                Accessible.ignored: true
                icon.name: card.iconName
                icon.source: card.placeholder
                icon.width: 44
                icon.height: 44
                icon.color: "transparent"
                background: null
            }

            ArtworkImage {
                anchors.centerIn: parent
                width: 44
                height: 44
                source: card.placeholder
                visible: !primary.visible && !alternate.visible && !localIcon.visible && !themedIcon.visible
            }
        }

        Label {
            id: titleLabel
            Layout.fillWidth: true
            color: card.cardText
            font.bold: card.running
            text: card.gameTitle
            textFormat: Text.PlainText
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }

        Label {
            Layout.fillWidth: true
            color: card.cardText
            text: card.gameStatus
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            Accessible.ignored: true
        }
    }
}
