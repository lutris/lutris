import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

// One setting in a group: its name and explanation, with the controls that change it beside them
Control {
    id: row

    property string title: ""
    property string subtitle: ""
    property color subtitleColor: Theme.textMuted
    // Controls on the right of the title
    default property alias controls: trailing.data
    // Content under the title, across the row
    property alias details: below.data

    Layout.fillWidth: true
    padding: 14
    topPadding: 12
    bottomPadding: 12

    background: Item {
        // The hairline between this row and the one above
        Rectangle {
            visible: row.y > 0
            x: 14
            width: parent.width - 28
            height: 1
            color: Theme.border
        }
    }

    contentItem: ColumnLayout {
        spacing: 0

        RowLayout {
            id: heading
            Layout.fillWidth: true
            spacing: 16

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Label {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: row.title
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                }

                Label {
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: row.subtitle
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    font.pointSize: Theme.smallSize
                    color: row.subtitleColor
                }
            }

            RowLayout {
                id: trailing
                spacing: 8
            }
        }

        ColumnLayout {
            id: below
            Layout.fillWidth: true
            // Rows without details keep no gap for them
            Layout.topMargin: implicitHeight > 0 && heading.implicitHeight > 0 ? 10 : 0
            spacing: 6
        }
    }
}
