import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

// A short label over artwork, such as a game's platform or state
Rectangle {
    id: pill

    property string text: ""
    property color dotColor: "transparent"

    implicitWidth: row.implicitWidth + 14
    implicitHeight: row.implicitHeight + 6
    radius: height / 2
    color: Qt.rgba(0.05, 0.05, 0.07, 0.78)
    border.color: Qt.rgba(1, 1, 1, 0.1)

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.leftMargin: 7
        anchors.rightMargin: 7
        spacing: 5

        Rectangle {
            visible: pill.dotColor.a > 0
            implicitWidth: 7
            implicitHeight: 7
            radius: 3.5
            color: pill.dotColor
        }

        Label {
            Layout.fillWidth: true
            text: pill.text
            textFormat: Text.PlainText
            elide: Text.ElideRight
            font.pointSize: Theme.smallSize * 0.92
            font.weight: Font.Medium
            color: "#f2f2f5"
            Accessible.ignored: true
        }
    }
}
