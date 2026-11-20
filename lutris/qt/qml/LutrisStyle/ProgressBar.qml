import QtQuick
import QtQuick.Templates as T

T.ProgressBar {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    contentItem: Item {
        implicitWidth: 160
        implicitHeight: 6
        clip: true

        Rectangle {
            id: bar

            // How far an indeterminate bar has travelled across the track
            property real phase: 0

            x: control.indeterminate ? phase * (parent.width + width) - width : 0
            width: control.indeterminate ? parent.width * 0.35 : control.visualPosition * parent.width
            height: parent.height
            radius: height / 2
            color: Theme.accent

            NumberAnimation on phase {
                running: control.indeterminate && control.visible
                loops: Animation.Infinite
                from: 0
                to: 1
                duration: 1200
                easing.type: Easing.InOutQuad
            }
        }
    }

    background: Rectangle {
        implicitWidth: 160
        implicitHeight: 6
        y: (control.height - height) / 2
        height: 6
        radius: 3
        color: Theme.track
    }
}
