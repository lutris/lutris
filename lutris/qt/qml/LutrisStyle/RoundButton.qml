import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.RoundButton {
    id: control

    readonly property color foreground: highlighted ? Theme.textOnAccent : Theme.text

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 8
    spacing: 6
    opacity: enabled ? 1 : 0.45

    icon.width: 18
    icon.height: 18
    icon.color: foreground

    contentItem: IconLabel {
        spacing: control.spacing
        mirrored: control.mirrored
        display: control.display
        icon: control.icon
        text: control.text
        font: control.font
        color: control.foreground
    }

    background: Rectangle {
        implicitWidth: Theme.controlHeight
        implicitHeight: Theme.controlHeight
        radius: control.radius
        color: control.highlighted ? (control.down ? Theme.accentPressed : control.hovered ? Theme.accentHover : Theme.accent)
             : control.down ? Theme.controlPressed : control.hovered ? Theme.controlHover : Theme.control
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accent
    }
}
