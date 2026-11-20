import QtQuick
import QtQuick.Templates as T

T.Label {
    id: control

    color: enabled ? Theme.text : Theme.textSubtle
    linkColor: Theme.accentText
}
