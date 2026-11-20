import QtQuick
import QtQuick.Templates as T

T.ToolTip {
    id: control

    x: parent ? (parent.width - implicitWidth) / 2 : 0
    y: -implicitHeight - 6

    implicitWidth: Math.min(380, Math.max(implicitBackgroundWidth + leftInset + rightInset,
                                          implicitContentWidth + leftPadding + rightPadding))
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    margins: 8
    padding: 7
    horizontalPadding: 10
    delay: 500

    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animation }
    }

    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 80 }
    }

    contentItem: Text {
        text: control.text
        font.pointSize: Theme.smallSize
        wrapMode: Text.Wrap
        color: Theme.text
    }

    background: Rectangle {
        radius: Theme.radiusSmall
        color: Theme.raised
        border.color: Theme.borderStrong
    }
}
