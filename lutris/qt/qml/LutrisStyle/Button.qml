import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.Button {
    id: control

    // A dialog's destructive button is drawn in the danger color, and the one that
    // answers it, such as OK or Yes, stands out as its primary button
    readonly property int role: T.DialogButtonBox.buttonRole
    readonly property bool destructive: role === T.DialogButtonBox.DestructiveRole
    readonly property bool primary: highlighted || role === T.DialogButtonBox.AcceptRole
                                    || role === T.DialogButtonBox.YesRole || role === T.DialogButtonBox.ApplyRole
    readonly property bool iconOnly: display === T.AbstractButton.IconOnly || text.length === 0
    readonly property color foreground: primary ? (destructive ? Theme.textOnDanger : Theme.textOnAccent)
                                                : destructive ? Theme.danger : Theme.text

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 7
    horizontalPadding: iconOnly ? padding : 14
    spacing: 7
    opacity: enabled ? 1 : 0.45
    font.weight: Font.Medium

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
        implicitWidth: control.iconOnly ? Theme.controlHeight : 72
        implicitHeight: Theme.controlHeight
        radius: Theme.radius
        visible: !control.flat || control.down || control.checked || control.hovered || control.visualFocus
        color: {
            if (control.primary) {
                if (control.destructive)
                    return control.down || control.hovered ? Theme.dangerHover : Theme.danger
                return control.down ? Theme.accentPressed : control.hovered ? Theme.accentHover : Theme.accent
            }
            if (control.flat)
                return control.down ? Theme.pressed : control.checked ? Theme.accentSubtle : Theme.hover
            return control.down ? Theme.controlPressed : control.checked ? Theme.accentSubtle
                 : control.hovered ? Theme.controlHover : Theme.control
        }
        border.width: control.visualFocus ? 2 : control.primary || control.flat ? 0 : 1
        border.color: control.visualFocus ? Theme.accent : Theme.border

        Behavior on color { ColorAnimation { duration: Theme.animation } }
    }
}
