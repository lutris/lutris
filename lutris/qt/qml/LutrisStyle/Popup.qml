import QtQuick
import QtQuick.Templates as T

T.Popup {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 12

    background: Rectangle {
        radius: Theme.radiusLarge
        color: Theme.raised
        border.color: Theme.borderStrong
    }

    T.Overlay.modal: Rectangle { color: Theme.scrim }
    T.Overlay.modeless: Rectangle { color: "transparent" }
}
