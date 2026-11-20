import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.Switch {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    padding: 4
    spacing: 10
    opacity: enabled ? 1 : 0.45

    indicator: Rectangle {
        implicitWidth: 40
        implicitHeight: 22
        x: control.text ? (control.mirrored ? control.width - width - control.rightPadding : control.leftPadding)
                        : control.leftPadding + (control.availableWidth - width) / 2
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: height / 2
        color: control.checked ? (control.down ? Theme.accentPressed : Theme.accent)
                               : control.hovered ? Theme.borderStrong : Theme.track
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accentHover

        Behavior on color { ColorAnimation { duration: Theme.animation } }

        Rectangle {
            readonly property real travel: parent.width - width - 6
            x: 3 + Math.max(0, Math.min(1, control.visualPosition)) * travel
            anchors.verticalCenter: parent.verticalCenter
            width: 16
            height: 16
            radius: 8
            color: control.checked ? Theme.textOnAccent : Theme.dark ? "#d8d9de" : "#ffffff"

            Behavior on x {
                enabled: !control.down
                NumberAnimation { duration: Theme.animation; easing.type: Easing.OutCubic }
            }
        }
    }

    contentItem: CheckLabel {
        leftPadding: control.indicator && !control.mirrored ? control.indicator.width + control.spacing : 0
        rightPadding: control.indicator && control.mirrored ? control.indicator.width + control.spacing : 0
        text: control.text
        font: control.font
        color: Theme.text
    }
}
