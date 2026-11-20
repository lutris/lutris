pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.impl
import QtQuick.Templates as T

T.ComboBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding,
                             implicitIndicatorHeight + topPadding + bottomPadding)

    padding: 6
    leftPadding: padding + (!control.mirrored || !indicator || !indicator.visible ? 0 : indicator.width + spacing)
    rightPadding: padding + (control.mirrored || !indicator || !indicator.visible ? 0 : indicator.width + spacing)
    opacity: enabled ? 1 : 0.45

    delegate: MenuItem {
        required property var model
        required property int index

        width: ListView.view.width
        text: model[control.textRole]
        checkable: true
        checked: control.currentIndex === index
        highlighted: control.highlightedIndex === index
        hoverEnabled: control.hoverEnabled
    }

    indicator: Icon {
        x: control.mirrored ? control.padding + 4 : control.width - width - control.padding - 4
        y: control.topPadding + (control.availableHeight - height) / 2
        symbol: "chevron-down"
        size: 16
        color: Theme.textMuted
    }

    contentItem: T.TextField {
        leftPadding: !control.mirrored ? 6 : control.editable && activeFocus ? 3 : 1
        rightPadding: control.mirrored ? 6 : control.editable && activeFocus ? 3 : 1
        topPadding: 0
        bottomPadding: 0

        text: control.editable ? control.editText : control.displayText

        enabled: control.editable
        autoScroll: control.editable
        readOnly: control.down
        inputMethodHints: control.inputMethodHints
        validator: control.validator
        selectByMouse: control.selectTextByMouse

        font: control.font
        color: Theme.text
        selectionColor: Theme.accent
        selectedTextColor: Theme.textOnAccent
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        implicitWidth: 160
        implicitHeight: Theme.controlHeight
        radius: Theme.radius
        color: control.editable ? Theme.field : control.down ? Theme.controlPressed
             : control.hovered ? Theme.controlHover : Theme.control
        border.width: control.visualFocus || (control.editable && control.activeFocus) ? 2 : 1
        border.color: control.visualFocus || (control.editable && control.activeFocus) ? Theme.accent : Theme.border
        visible: !control.flat || control.down

        Behavior on color { ColorAnimation { duration: Theme.animation } }
    }

    popup: T.Popup {
        y: control.height + 4
        width: Math.max(control.width, 180)
        height: Math.min(contentItem.implicitHeight + topPadding + bottomPadding,
                         control.Window.height - topMargin - bottomMargin)
        topMargin: 8
        bottomMargin: 8
        padding: 5
        font: control.font

        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animation }
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: control.delegateModel
            currentIndex: control.highlightedIndex
            highlightMoveDuration: 0
            boundsBehavior: Flickable.StopAtBounds

            T.ScrollIndicator.vertical: ScrollIndicator {}
        }

        background: Rectangle {
            radius: Theme.radiusLarge
            color: Theme.raised
            border.color: Theme.borderStrong
        }
    }
}
