import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.SpinBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            contentItem.implicitWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             up.implicitIndicatorHeight, down.implicitIndicatorHeight)

    leftPadding: padding + (control.mirrored ? (up.indicator ? up.indicator.width : 0) : (down.indicator ? down.indicator.width : 0))
    rightPadding: padding + (control.mirrored ? (down.indicator ? down.indicator.width : 0) : (up.indicator ? up.indicator.width : 0))
    opacity: enabled ? 1 : 0.45

    validator: IntValidator {
        locale: control.locale.name
        bottom: Math.min(control.from, control.to)
        top: Math.max(control.from, control.to)
    }

    contentItem: TextInput {
        z: 2
        text: control.displayText
        clip: width < implicitWidth
        padding: 6

        font: control.font
        color: Theme.text
        selectionColor: Theme.accent
        selectedTextColor: Theme.textOnAccent
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter

        readOnly: !control.editable
        validator: control.validator
        inputMethodHints: control.inputMethodHints
    }

    up.indicator: Rectangle {
        x: control.mirrored ? 2 : control.width - width - 2
        y: 2
        implicitWidth: 30
        implicitHeight: Theme.controlHeight - 4
        radius: Theme.radiusSmall
        color: control.up.pressed ? Theme.pressed : control.up.hovered ? Theme.hover : "transparent"

        Icon {
            anchors.centerIn: parent
            symbol: "plus"
            size: 14
            color: Theme.textMuted
        }
    }

    down.indicator: Rectangle {
        x: control.mirrored ? control.width - width - 2 : 2
        y: 2
        implicitWidth: 30
        implicitHeight: Theme.controlHeight - 4
        radius: Theme.radiusSmall
        color: control.down.pressed ? Theme.pressed : control.down.hovered ? Theme.hover : "transparent"

        Icon {
            anchors.centerIn: parent
            symbol: "minus"
            size: 14
            color: Theme.textMuted
        }
    }

    background: Rectangle {
        implicitWidth: 130
        implicitHeight: Theme.controlHeight
        radius: Theme.radius
        color: Theme.field
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.border
    }
}
