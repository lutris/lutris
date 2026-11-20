import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "gameCategories"

    required property QtObject controller
    required property string targetGameId

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(430, parent.width - 32)
    title: qsTr("Game Categories")
    modal: true
    standardButtons: Dialog.Close

    contentItem: ColumnLayout {
        spacing: 10

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(220, categoryList.implicitHeight)
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                id: categoryList
                width: parent.width

                Repeater {
                    model: dialog.controller.categoryModel
                    delegate: CheckBox {
                        required property string categoryName
                        required property bool included
                        Layout.fillWidth: true
                        text: categoryName
                        checked: included
                        onToggled: dialog.controller.set_category(dialog.targetGameId, categoryName, checked)
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true

            TextField {
                id: newCategory
                objectName: "newGameCategory"
                Layout.fillWidth: true
                placeholderText: qsTr("New category")
                Accessible.name: placeholderText
                onAccepted: if (addButton.enabled) addButton.clicked()
            }

            Button {
                id: addButton
                text: qsTr("Add")
                enabled: dialog.controller.organizationReady && newCategory.text.trim().length > 0
                onClicked: {
                    dialog.controller.set_category(dialog.targetGameId, newCategory.text, true)
                    newCategory.clear()
                    newCategory.forceActiveFocus()
                }
            }
        }
    }
}
