pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

// A game's cover, banner and icon, each of which can be replaced or reset
ColumnLayout {
    id: editor
    objectName: "gameArtworkEditor"

    required property QtObject artwork

    spacing: 8

    NativeDialogs.FileDialog {
        id: picker

        property string kind: ""

        title: qsTr("Choose an image")
        nameFilters: [qsTr("Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)"), qsTr("All files (*)")]
        onAccepted: editor.artwork.choose_file(kind, selectedFile)
    }

    Label {
        text: qsTr("Artwork")
        font.weight: Font.DemiBold
    }

    Flow {
        Layout.fillWidth: true
        spacing: 16

        Repeater {
            model: editor.artwork.images

            ColumnLayout {
                id: slot

                required property var modelData
                readonly property size frame: modelData.kind === "cover" ? Qt.size(120, 180)
                                            : modelData.kind === "banner" ? Qt.size(230, 107) : Qt.size(96, 96)

                spacing: 4

                Label {
                    text: slot.modelData.custom ? qsTr("%1 (custom)").arg(slot.modelData.label) : slot.modelData.label
                    font.pointSize: Theme.smallSize
                    color: Theme.textMuted
                }

                Rectangle {
                    implicitWidth: slot.frame.width
                    implicitHeight: slot.frame.height
                    radius: Theme.radius
                    color: Theme.surface
                    border.color: Theme.border

                    Image {
                        objectName: "artworkImage_" + slot.modelData.kind
                        anchors.fill: parent
                        anchors.margins: 6
                        source: slot.modelData.url
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                    }

                    Icon {
                        anchors.centerIn: parent
                        visible: slot.modelData.url.toString().length === 0
                        symbol: "image"
                        size: 28
                        color: Theme.textSubtle
                    }

                    BusyIndicator {
                        anchors.centerIn: parent
                        running: slot.modelData.working
                        visible: running
                    }
                }

                Button {
                    Layout.fillWidth: true
                    text: qsTr("Choose File…")
                    icon.source: Theme.icon("folder")
                    enabled: !editor.artwork.working
                    Accessible.name: qsTr("Choose a file for the %1").arg(slot.modelData.label)
                    onClicked: {
                        picker.kind = slot.modelData.kind
                        picker.open()
                    }
                }

                Button {
                    objectName: "steamGridDbArtwork_" + slot.modelData.kind
                    Layout.fillWidth: true
                    text: qsTr("SteamGridDB…")
                    icon.source: Theme.icon("image")
                    enabled: !editor.artwork.working && !editor.artwork.loadingChoices
                    Accessible.name: qsTr("Choose the %1 from SteamGridDB").arg(slot.modelData.label)
                    onClicked: {
                        editor.artwork.load_choices(slot.modelData.kind)
                        chooser.open()
                    }
                }

                Button {
                    objectName: "resetArtwork_" + slot.modelData.kind
                    Layout.fillWidth: true
                    flat: true
                    text: qsTr("Reset")
                    icon.source: Theme.icon("refresh")
                    enabled: !editor.artwork.working
                    Accessible.name: qsTr("Reset the %1").arg(slot.modelData.label)
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("Use the artwork from the game's store or SteamGridDB again")
                    onClicked: editor.artwork.reset(slot.modelData.kind)
                }
            }
        }
    }

    Dialog {
        id: chooser
        objectName: "steamGridDbChooser"

        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(760, parent.width - 32)
        height: Math.min(560, parent.height - 32)
        modal: true
        title: qsTr("Choose from SteamGridDB")
        standardButtons: Dialog.Close

        contentItem: ColumnLayout {
            ProgressBar {
                Layout.fillWidth: true
                visible: editor.artwork.loadingChoices
                indeterminate: true
                Accessible.name: qsTr("Looking for artwork…")
            }

            GridView {
                id: grid
                objectName: "steamGridDbChoices"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: editor.artwork.choices
                cellWidth: editor.artwork.choicesKind === "banner" ? 240 : editor.artwork.choicesKind === "icon" ? 112 : 136
                cellHeight: editor.artwork.choicesKind === "banner" ? 128 : editor.artwork.choicesKind === "icon" ? 112 : 212
                ScrollBar.vertical: ScrollBar {}

                delegate: ItemDelegate {
                    id: choice

                    required property var modelData
                    required property int index

                    objectName: "steamGridDbChoice" + index
                    width: grid.cellWidth - 8
                    height: grid.cellHeight - 8
                    Accessible.name: qsTr("%1 × %2 image").arg(modelData.width).arg(modelData.height)
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("%1 × %2").arg(modelData.width).arg(modelData.height)

                    contentItem: Image {
                        source: choice.modelData.thumbnail
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }

                    onClicked: {
                        editor.artwork.choose_url(modelData.url)
                        chooser.close()
                    }
                }
            }
        }
    }
}
