pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

// One option of a configuration page; the editor depends on the option's type
ItemDelegate {
    id: option

    required property QtObject controller
    required property string optionSection
    required property string optionKey
    required property string optionType
    required property string optionLabel
    required property string optionHelp
    required property var optionValue
    required property string defaultLabel
    required property var choices
    required property int minimum
    required property int maximum
    required property bool optionEnabled
    required property bool setHere
    required property bool changedBelow
    required property string warning
    required property string error

    objectName: "configOption_" + optionKey
    hoverEnabled: true
    padding: 8
    horizontalPadding: 10

    background: Rectangle {
        radius: Theme.radius
        color: option.hovered ? Theme.hover : "transparent"
    }

    function commit(value: var): void {
        controller.set_value(optionSection, optionKey, value)
    }

    ToolTip.visible: hovered && ToolTip.text.length > 0
    ToolTip.delay: 600
    ToolTip.text: {
        let text = optionHelp
        if (defaultLabel.length > 0)
            text += (text.length > 0 ? "\n\n" : "") + qsTr("Default: %1").arg(defaultLabel)
        if (changedBelow)
            text += (text.length > 0 ? "\n\n" : "") + qsTr("A lower configuration level changes this option.")
        return text
    }

    contentItem: ColumnLayout {
        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            RowLayout {
                Layout.preferredWidth: option.optionType === "label" ? -1 : Math.min(280, option.width * 0.36)
                Layout.maximumWidth: option.optionType === "label" ? -1 : Math.min(280, option.width * 0.36)
                Layout.fillWidth: option.optionType === "label"
                spacing: 8

                // Marks the options this configuration level sets
                Rectangle {
                    implicitWidth: 6
                    implicitHeight: 6
                    radius: 3
                    color: Theme.accent
                    visible: option.setHere
                }

                Label {
                    Layout.fillWidth: true
                    text: option.optionLabel
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    font.weight: option.setHere ? Font.DemiBold : Font.Normal
                    font.italic: option.changedBelow
                    color: option.optionType === "label" ? Theme.textMuted : Theme.text
                    enabled: option.optionEnabled
                }
            }

            Loader {
                id: editor
                Layout.fillWidth: true
                enabled: option.optionEnabled
                visible: option.optionType !== "label"
                sourceComponent: {
                    switch (option.optionType) {
                    case "bool": return boolEditor
                    case "range": return rangeEditor
                    case "choice": return choiceEditor
                    case "choice_with_entry":
                    case "choice_with_search": return editableChoiceEditor
                    case "file": return fileEditor
                    case "directory": return directoryEditor
                    case "multiple_file": return filesEditor
                    case "mapping": return mappingEditor
                    case "label": return null
                    default: return textEditor
                    }
                }
            }

            ToolButton {
                objectName: "resetOption_" + option.optionKey
                icon.source: Theme.icon("refresh")
                visible: option.setHere
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Reset option to global or default config")
                Accessible.name: qsTr("Reset %1").arg(option.optionLabel)
                onClicked: option.controller.reset(option.optionSection, option.optionKey)
            }
        }

        Label {
            Layout.fillWidth: true
            visible: text.length > 0
            text: option.error || option.warning
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.pointSize: Theme.smallSize
            color: option.error ? Theme.danger : Theme.warning
        }
    }

    Component {
        id: textEditor

        TextField {
            text: String(option.optionValue ?? "")
            selectByMouse: true
            Accessible.name: option.optionLabel
            onEditingFinished: if (text !== String(option.optionValue ?? "")) option.commit(text)
        }
    }

    Component {
        id: boolEditor

        Item {
            implicitHeight: toggle.implicitHeight

            Switch {
                id: toggle
                objectName: "optionSwitch_" + option.optionKey
                checked: option.optionValue === true
                Accessible.name: option.optionLabel
                onToggled: option.commit(checked)
            }
        }
    }

    Component {
        id: rangeEditor

        Item {
            implicitHeight: spin.implicitHeight

            SpinBox {
                id: spin
                from: option.minimum
                to: option.maximum
                value: Number(option.optionValue)
                editable: true
                Accessible.name: option.optionLabel
                onValueModified: option.commit(value)
            }
        }
    }

    Component {
        id: choiceEditor

        ComboBox {
            id: choice
            objectName: "optionChoice_" + option.optionKey
            model: option.choices
            textRole: "label"
            valueRole: "value"
            Accessible.name: option.optionLabel
            onModelChanged: currentIndex = indexOfValue(option.optionValue)
            Component.onCompleted: currentIndex = indexOfValue(option.optionValue)
            onActivated: if (currentValue !== option.optionValue) option.commit(currentValue)

            Connections {
                target: option
                function onOptionValueChanged() { choice.currentIndex = choice.indexOfValue(option.optionValue) }
            }
        }
    }

    Component {
        id: editableChoiceEditor

        ComboBox {
            id: editableChoice
            editable: true
            model: option.choices
            textRole: "label"
            valueRole: "value"
            Accessible.name: option.optionLabel
            Component.onCompleted: {
                currentIndex = indexOfValue(option.optionValue)
                if (currentIndex < 0)
                    editText = String(option.optionValue ?? "")
            }
            onActivated: if (currentValue !== option.optionValue) option.commit(currentValue)
            onAccepted: {
                const index = find(editText)
                const value = index >= 0 ? valueAt(index) : editText
                if (value !== option.optionValue)
                    option.commit(value)
            }
        }
    }

    Component {
        id: fileEditor

        RowLayout {
            TextField {
                id: path
                Layout.fillWidth: true
                text: String(option.optionValue ?? "")
                selectByMouse: true
                Accessible.name: option.optionLabel
                onEditingFinished: if (text !== String(option.optionValue ?? "")) option.commit(text)
            }

            Button {
                text: qsTr("Browse…")
                icon.source: Theme.icon("folder")
                Accessible.name: qsTr("Browse for %1").arg(option.optionLabel)
                onClicked: filePicker.open()
            }

            NativeDialogs.FileDialog {
                id: filePicker
                title: option.optionLabel
                onAccepted: option.commit(option.controller.local_path(selectedFile))
            }
        }
    }

    Component {
        id: directoryEditor

        RowLayout {
            TextField {
                Layout.fillWidth: true
                text: String(option.optionValue ?? "")
                selectByMouse: true
                Accessible.name: option.optionLabel
                onEditingFinished: if (text !== String(option.optionValue ?? "")) option.commit(text)
            }

            Button {
                text: qsTr("Browse…")
                icon.source: Theme.icon("folder")
                Accessible.name: qsTr("Browse for %1").arg(option.optionLabel)
                onClicked: folderPicker.open()
            }

            NativeDialogs.FolderDialog {
                id: folderPicker
                title: option.optionLabel
                onAccepted: option.commit(option.controller.local_path(selectedFolder))
            }
        }
    }

    Component {
        id: filesEditor

        ColumnLayout {
            Repeater {
                model: option.optionValue

                RowLayout {
                    id: fileRow

                    required property string modelData
                    required property int index

                    Layout.fillWidth: true

                    Label {
                        Layout.fillWidth: true
                        text: fileRow.modelData
                        textFormat: Text.PlainText
                        elide: Text.ElideMiddle
                    }

                    ToolButton {
                        icon.source: Theme.icon("close")
                        Accessible.name: qsTr("Remove %1").arg(fileRow.modelData)
                        onClicked: {
                            const files = Array.from(option.optionValue)
                            files.splice(fileRow.index, 1)
                            option.commit(files)
                        }
                    }
                }
            }

            Button {
                text: qsTr("Add Files…")
                icon.source: Theme.icon("plus")
                onClicked: filesPicker.open()
            }

            NativeDialogs.FileDialog {
                id: filesPicker
                title: option.optionLabel
                fileMode: NativeDialogs.FileDialog.OpenFiles
                onAccepted: option.commit(Array.from(option.optionValue).concat(option.controller.local_paths(selectedFiles)))
            }
        }
    }

    Component {
        id: mappingEditor

        ColumnLayout {
            id: mapping

            property var rows: Array.from(option.optionValue).map(row => ({ name: row.name, value: row.value }))

            function commitRows(): void {
                option.controller.set_mapping(option.optionSection, option.optionKey, rows)
            }

            Repeater {
                model: mapping.rows.length

                RowLayout {
                    id: mappingRow

                    required property int index

                    Layout.fillWidth: true

                    TextField {
                        Layout.preferredWidth: 160
                        text: mapping.rows[mappingRow.index].name
                        placeholderText: qsTr("Name")
                        Accessible.name: qsTr("Variable name")
                        onEditingFinished: if (text !== mapping.rows[mappingRow.index].name) {
                            mapping.rows[mappingRow.index].name = text
                            mapping.commitRows()
                        }
                    }

                    TextField {
                        Layout.fillWidth: true
                        text: mapping.rows[mappingRow.index].value
                        placeholderText: qsTr("Value")
                        Accessible.name: qsTr("Variable value")
                        onEditingFinished: if (text !== mapping.rows[mappingRow.index].value) {
                            mapping.rows[mappingRow.index].value = text
                            mapping.commitRows()
                        }
                    }

                    ToolButton {
                        icon.source: Theme.icon("close")
                        Accessible.name: qsTr("Remove")
                        onClicked: {
                            mapping.rows.splice(mappingRow.index, 1)
                            mapping.commitRows()
                        }
                    }
                }
            }

            Button {
                text: qsTr("Add")
                icon.source: Theme.icon("plus")
                // A row without a name isn't saved, so it only lives here until it gets one
                onClicked: mapping.rows = mapping.rows.concat([{ name: "", value: "" }])
            }
        }
    }
}
