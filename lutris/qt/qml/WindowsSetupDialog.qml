pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Dialog {
    id: dialog

    required property QtObject controller

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(440, parent.width - 32)
    title: qsTr("Run Windows Setup")
    modal: true
    standardButtons: Dialog.Cancel
    onOpened: setupName.forceActiveFocus()
    onClosed: {
        setupName.clear()
        windowsVersion.currentIndex = 0
        setupLocale.currentIndex = 0
    }

    contentItem: ColumnLayout {
        Label { text: qsTr("Game name") }

        TextField {
            id: setupName
            Layout.fillWidth: true
            Accessible.name: qsTr("Game name")
            onAccepted: if (text.trim().length > 0) setupFile.open()
        }

        Label { text: qsTr("Windows version") }

        ComboBox {
            id: windowsVersion
            Layout.fillWidth: true
            model: dialog.controller.windowsSetupPresets
            textRole: "label"
            valueRole: "value"
            Accessible.name: qsTr("Windows version")
        }

        Label { text: qsTr("Locale") }

        ComboBox {
            id: setupLocale
            Layout.fillWidth: true
            model: dialog.controller.windowsSetupLocales
            textRole: "label"
            valueRole: "value"
            Accessible.name: qsTr("Locale")
        }

        Button {
            text: qsTr("Choose Setup Executable…")
            enabled: setupName.text.trim().length > 0
            onClicked: setupFile.open()
        }
    }

    NativeDialogs.FileDialog {
        id: setupFile

        title: qsTr("Choose a Windows setup executable")
        nameFilters: [qsTr("Windows executables (*.exe *.EXE)")]
        onAccepted: {
            const name = setupName.text
            const version = windowsVersion.currentValue
            const locale = setupLocale.currentValue
            dialog.accept()
            dialog.controller.open_windows_setup(name, selectedFile, version, locale)
        }
    }
}
