import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.ToolButton {
    id: control

    readonly property bool iconOnly: display === T.AbstractButton.IconOnly || text.length === 0
    readonly property color foreground: highlighted || checked ? Theme.accentText : Theme.text

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 7
    horizontalPadding: iconOnly ? padding : 11
    spacing: 7
    flat: true
    opacity: enabled ? 1 : 0.4

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
        radius: Theme.radius
        color: control.down ? Theme.pressed : control.checked || control.highlighted ? Theme.accentSubtle
             : control.hovered ? Theme.hover : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accent

        Behavior on color { ColorAnimation { duration: Theme.animation } }
    }
}
