import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.MenuItem {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    // Hidden items leave no gap in the menu
    height: visible ? implicitHeight : 0
    padding: 6
    horizontalPadding: 10
    spacing: 10
    opacity: enabled ? 1 : 0.4

    icon.width: 18
    icon.height: 18
    icon.color: Theme.textMuted

    contentItem: IconLabel {
        readonly property real arrowPadding: control.subMenu && control.arrow ? control.arrow.width + control.spacing : 0
        readonly property real indicatorPadding: control.checkable && control.indicator ? control.indicator.width + control.spacing : 0

        leftPadding: !control.mirrored ? indicatorPadding : arrowPadding
        rightPadding: control.mirrored ? indicatorPadding : arrowPadding
        spacing: control.spacing
        mirrored: control.mirrored
        display: control.display
        alignment: Qt.AlignLeft
        icon: control.icon
        text: control.text
        font: control.font
        color: Theme.text
    }

    indicator: Icon {
        x: control.mirrored ? control.width - width - control.rightPadding : control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        visible: control.checkable
        opacity: control.checked ? 1 : 0
        symbol: "check"
        size: 16
        color: Theme.accentText
    }

    arrow: Icon {
        x: control.mirrored ? control.leftPadding : control.width - width - control.rightPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        visible: control.subMenu
        mirror: control.mirrored
        symbol: "chevron-right"
        size: 16
        color: Theme.textMuted
    }

    background: Rectangle {
        implicitWidth: 210
        implicitHeight: 32
        radius: Theme.radiusSmall
        color: control.down ? Theme.pressed : control.highlighted ? Theme.hover : "transparent"
    }
}
