import QtQuick

// The box of check boxes and check delegates
Rectangle {
    id: indicator

    required property int checkState
    required property bool down
    required property bool hovered
    required property bool visualFocus
    readonly property bool on: checkState !== Qt.Unchecked

    implicitWidth: 18
    implicitHeight: 18
    radius: 5
    color: on ? (down ? Theme.accentPressed : Theme.accent) : Theme.field
    border.width: on ? 0 : visualFocus ? 2 : 1.5
    border.color: visualFocus ? Theme.accent : hovered ? Theme.textSubtle : Theme.borderStrong

    Behavior on color { ColorAnimation { duration: Theme.animation } }

    Icon {
        anchors.centerIn: parent
        symbol: "check"
        size: 14
        color: Theme.textOnAccent
        visible: indicator.checkState === Qt.Checked
    }

    Rectangle {
        anchors.centerIn: parent
        width: 9
        height: 2
        radius: 1
        color: Theme.textOnAccent
        visible: indicator.checkState === Qt.PartiallyChecked
    }
}
