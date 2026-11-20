import QtQuick
import QtQuick.Controls.impl
import QtQuick.Controls.Basic.impl
import QtQuick.Templates as T

T.TextArea {
    id: control

    implicitWidth: Math.max(contentWidth + leftPadding + rightPadding,
                            implicitBackgroundWidth + leftInset + rightInset,
                            placeholder.implicitWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(contentHeight + topPadding + bottomPadding,
                             implicitBackgroundHeight + topInset + bottomInset,
                             placeholder.implicitHeight + topPadding + bottomPadding)

    padding: 10
    leftPadding: 12
    rightPadding: 12

    color: Theme.text
    placeholderTextColor: Theme.textSubtle
    selectionColor: Theme.accent
    selectedTextColor: Theme.textOnAccent
    selectByMouse: true

    ContextMenu.menu: TextEditingContextMenu {
        editor: control
    }

    PlaceholderText {
        id: placeholder
        x: control.leftPadding
        y: control.topPadding
        width: control.width - (control.leftPadding + control.rightPadding)
        height: control.height - (control.topPadding + control.bottomPadding)

        text: control.placeholderText
        font: control.font
        color: control.placeholderTextColor
        verticalAlignment: control.verticalAlignment
        visible: !control.length && !control.preeditText
        wrapMode: control.wrapMode
        elide: Text.ElideRight
        renderType: control.renderType
    }

    background: Rectangle {
        radius: Theme.radius
        color: Theme.field
        border.width: control.activeFocus && !control.readOnly ? 2 : 1
        border.color: control.activeFocus && !control.readOnly ? Theme.accent : Theme.border
    }
}
