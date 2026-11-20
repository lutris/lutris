import QtQuick
import QtQuick.Effects

// Artwork that fills its frame, with its corners rounded where the renderer can
Item {
    id: artwork

    property alias source: image.source
    property alias fillMode: image.fillMode
    readonly property alias status: image.status
    property real radius: 0

    // The software renderer can't run the shader that rounds the corners
    readonly property bool rounded: radius > 0 && GraphicsInfo.api !== GraphicsInfo.Software
                                    && GraphicsInfo.api !== GraphicsInfo.Unknown

    Accessible.ignored: true

    Image {
        id: image
        anchors.fill: parent
        visible: !artwork.rounded
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: artwork.width * Screen.devicePixelRatio
        sourceSize.height: artwork.height * Screen.devicePixelRatio
        asynchronous: true
        smooth: true
        mipmap: true
    }

    Loader {
        anchors.fill: parent
        active: artwork.rounded && image.status === Image.Ready
        sourceComponent: MultiEffect {
            source: image
            maskEnabled: true
            maskSource: mask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }
    }

    Rectangle {
        id: mask
        width: artwork.width
        height: artwork.height
        radius: artwork.radius
        visible: false
        layer.enabled: artwork.rounded
        layer.smooth: true
    }
}
