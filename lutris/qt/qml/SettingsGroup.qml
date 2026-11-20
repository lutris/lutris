import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

// A titled card of settings, whose rows are separated by hairlines
ColumnLayout {
    id: group

    property string title: ""
    property string description: ""
    default property alias rows: column.data

    Layout.fillWidth: true
    spacing: 8

    Label {
        Layout.fillWidth: true
        Layout.leftMargin: 2
        visible: text.length > 0
        text: group.title
        font.weight: Font.DemiBold
        elide: Text.ElideRight
    }

    Label {
        Layout.fillWidth: true
        Layout.leftMargin: 2
        visible: text.length > 0
        text: group.description
        wrapMode: Text.WordWrap
        font.pointSize: Theme.smallSize
        color: Theme.textMuted
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: column.implicitHeight
        radius: Theme.radiusLarge
        color: Theme.surface
        border.color: Theme.border

        ColumnLayout {
            id: column
            anchors.left: parent.left
            anchors.right: parent.right
            spacing: 0
        }
    }
}
