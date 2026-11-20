import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "launchConfigurationDialog"

    required property QtObject prompts
    property list<string> configurationNames
    property int selectedIndex: 0
    property bool remembered: false

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(460, parent.width - 32)
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel
    onOpened: configuration.forceActiveFocus()
    onAccepted: prompts.answer_configuration(configuration.currentIndex, remember.checked)
    onRejected: prompts.answer(false, "")

    contentItem: ColumnLayout {
        Label {
            text: qsTr("Launch configuration")
        }

        ComboBox {
            id: configuration
            objectName: "launchConfigurationChoice"
            Layout.fillWidth: true
            Accessible.name: qsTr("Launch configuration")
            model: dialog.configurationNames
            currentIndex: dialog.selectedIndex
        }

        CheckBox {
            id: remember
            objectName: "rememberLaunchConfiguration"
            text: qsTr("Remember this choice")
            checked: dialog.remembered
        }
    }
}
