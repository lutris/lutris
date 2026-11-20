import QtQuick
import QtQuick.Controls.impl

// One icon of the style's icon set, tinted to match the text around it
IconImage {
    property string symbol: ""
    property int size: 18

    source: Theme.icon(symbol)
    sourceSize: Qt.size(size, size)
    color: Theme.text
    Accessible.ignored: true
}
