import QtQuick
import QtQuick.Controls
import QtQuick.Controls.impl
import QtQuick.Layouts
import LutrisStyle

ItemDelegate {
    id: card

    required property int index
    required property string gameTitle
    required property string runnerText
    required property string platformText
    required property string playTimeText
    required property string lastPlayedText
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
    required property bool showTitle
    required property bool showBadges

    readonly property string gameStatus: running ? qsTr("Running") : installed ? "" : qsTr("Not installed")
    readonly property string badgeText: showBadges && platformText.length > 0
                                        ? (gameStatus.length > 0 && !running ? qsTr("%1 · %2").arg(platformText).arg(gameStatus) : platformText)
                                        : (showBadges && !running ? gameStatus : "")
    readonly property url primaryArtwork: banners ? bannerUrl : coverUrl
    readonly property url alternateArtwork: banners ? coverUrl : bannerUrl
    readonly property bool hasArtwork: primary.status === Image.Ready || alternate.status === Image.Ready
    // The frame's height for its width: covers stand like boxes, banners lie like store headers
    readonly property real artworkRatio: banners ? 69 / 184 : 4 / 3

    signal menuRequested()

    focusPolicy: Qt.NoFocus
    hoverEnabled: true
    padding: 8
    topPadding: 8
    bottomPadding: 6
    Accessible.name: gameTitle
    Accessible.description: gameStatus
    ToolTip.visible: hovered && (!showTitle || titleLabel.truncated)
    ToolTip.text: gameTitle

    background: null

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: card.menuRequested()
    }

    contentItem: ColumnLayout {
        spacing: 8

        Item {
            id: frame
            Layout.fillWidth: true
            Layout.preferredHeight: width * card.artworkRatio

            transform: Translate {
                y: card.hovered && !card.pressed ? -3 : 0
                Behavior on y { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            }

            // The selection ring, with a gap between it and the artwork
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: Theme.radiusLarge + 4
                color: "transparent"
                border.width: 2
                border.color: card.keyboardFocus ? Theme.accentHover : Theme.accent
                opacity: card.selected ? 1 : 0

                Behavior on opacity { NumberAnimation { duration: Theme.animation } }
            }

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusLarge
                gradient: Gradient {
                    GradientStop { position: 0; color: Theme.dark ? "#2a2c33" : "#e9e9ee" }
                    GradientStop { position: 1; color: Theme.dark ? "#1c1d22" : "#dcdce3" }
                }
                border.color: Theme.border
                visible: !card.hasArtwork
            }

            Item {
                anchors.fill: parent
                // Games that aren't installed fade into the background
                opacity: card.installed || card.running ? 1 : 0.5

                ArtworkImage {
                    id: primary
                    anchors.fill: parent
                    radius: Theme.radiusLarge
                    source: card.primaryArtwork
                    visible: status === Image.Ready
                }

                ArtworkImage {
                    id: alternate
                    anchors.fill: parent
                    radius: Theme.radiusLarge
                    source: primary.status === Image.Null || primary.status === Image.Error ? card.alternateArtwork : ""
                    visible: status === Image.Ready
                }

                // Without artwork, the game's icon and name stand in for it
                ColumnLayout {
                    anchors.centerIn: parent
                    width: parent.width - 24
                    visible: !card.hasArtwork
                    spacing: 10

                    Item {
                        Layout.alignment: Qt.AlignHCenter
                        implicitWidth: card.banners ? 36 : 52
                        implicitHeight: implicitWidth

                        ArtworkImage {
                            id: localIcon
                            anchors.fill: parent
                            fillMode: Image.PreserveAspectFit
                            source: card.hasArtwork ? "" : card.iconUrl
                            visible: status === Image.Ready
                        }

                        IconImage {
                            anchors.fill: parent
                            visible: !localIcon.visible
                            name: card.iconName
                            source: card.placeholder
                            sourceSize: Qt.size(width * 2, height * 2)
                            color: "transparent"
                            Accessible.ignored: true
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        visible: !card.showTitle
                        text: card.gameTitle
                        textFormat: Text.PlainText
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                        font.weight: Font.DemiBold
                        color: Theme.textMuted
                        Accessible.ignored: true
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: Theme.radiusLarge
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, Theme.dark ? 0.08 : 0)
                visible: card.hasArtwork
            }

            // The running game's pulse
            Pill {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 8
                visible: card.running
                text: qsTr("Running")
                dotColor: Theme.success
            }

            Pill {
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.margins: 8
                width: Math.min(implicitWidth, parent.width - 16)
                visible: text.length > 0
                text: card.badgeText
            }
        }

        Label {
            id: titleLabel
            visible: card.showTitle
            Layout.fillWidth: true
            Layout.leftMargin: 2
            Layout.rightMargin: 2
            text: card.gameTitle
            textFormat: Text.PlainText
            font.weight: card.selected ? Font.DemiBold : Font.Medium
            color: card.selected ? Theme.text : card.installed ? Theme.text : Theme.textMuted
            horizontalAlignment: card.banners ? Text.AlignLeft : Text.AlignHCenter
            elide: Text.ElideRight
        }
    }
}
