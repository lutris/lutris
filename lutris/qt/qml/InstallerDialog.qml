pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

Dialog {
    id: dialog
    objectName: "installerDialog"

    required property QtObject controller
    readonly property QtObject installation: controller.installation

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(680, parent.width - 48)
    height: Math.min(560, parent.height - 48)
    title: controller.title
    modal: true
    closePolicy: installation.running ? Popup.NoAutoClose : Popup.CloseOnEscape

    Connections {
        target: dialog.controller
        function onCloseRequested() { dialog.close() }
    }

    NativeDialogs.FolderDialog {
        id: picker
        title: qsTr("Choose Installation Folder")
        onAccepted: dialog.controller.choose_directory(selectedFolder)
    }

    Dialog {
        id: cancelConfirmation
        objectName: "cancelInstallationDialog"
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: qsTr("Cancel installation?")
        standardButtons: Dialog.Yes | Dialog.No

        ColumnLayout {
            Label { text: qsTr("Are you sure you want to cancel the installation?") }

            CheckBox {
                id: removeFiles
                objectName: "removeInstallationFiles"
                visible: dialog.installation.canRemoveFiles
                checked: true
                text: qsTr("Remove game files")
            }
        }

        onAccepted: dialog.installation.cancel(removeFiles.checked && dialog.installation.canRemoveFiles)
    }

    contentItem: StackLayout {
        currentIndex: dialog.installation.active ? 2 : dialog.controller.selected ? 1 : 0

        ColumnLayout {
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: dialog.controller.choices.length === 0 ? qsTr("Looking for installers…")
                        : qsTr("Choose an installer.")
                wrapMode: Text.WordWrap
                color: Theme.textMuted
            }

            ProgressBar {
                Layout.fillWidth: true
                visible: dialog.controller.loading
                indeterminate: visible
                Accessible.name: qsTr("Looking for installers…")
            }

            ListView {
                objectName: "installerChoices"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 8
                boundsBehavior: Flickable.StopAtBounds
                model: dialog.controller.choices
                ScrollBar.vertical: ScrollBar {}

                delegate: Frame {
                    id: choice

                    required property var modelData

                    width: ListView.view.width

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 4

                        RowLayout {
                            Layout.fillWidth: true

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0

                                Label {
                                    Layout.fillWidth: true
                                    text: choice.modelData.version
                                    textFormat: Text.PlainText
                                    font.pointSize: Theme.largeSize
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                Label {
                                    Layout.fillWidth: true
                                    text: choice.modelData.runnerName
                                    textFormat: Text.PlainText
                                    font.pointSize: Theme.smallSize
                                    color: Theme.accentText
                                    elide: Text.ElideRight
                                }
                            }

                            Button {
                                objectName: "chooseInstaller" + choice.modelData.id
                                highlighted: true
                                text: qsTr("Choose")
                                enabled: !dialog.controller.loading
                                Accessible.name: qsTr("Choose %1").arg(choice.modelData.version)
                                onClicked: dialog.controller.select(choice.modelData.id)
                            }
                        }

                        Repeater {
                            model: [choice.modelData.description, choice.modelData.credits, choice.modelData.notes]

                            Label {
                                required property string modelData

                                Layout.fillWidth: true
                                visible: modelData.length > 0
                                text: modelData
                                textFormat: Text.PlainText
                                wrapMode: Text.Wrap
                                font.pointSize: Theme.smallSize
                                color: Theme.textMuted
                            }
                        }
                    }
                }
            }
        }

        ColumnLayout {
            spacing: 8

            Label {
                objectName: "installerSummary"
                Layout.fillWidth: true
                font.pointSize: Theme.largeSize
                text: dialog.controller.requiredGame.length > 0
                        ? qsTr("This installer needs %1 to be installed first.").arg(dialog.controller.requiredGame)
                        : qsTr("Installer: %1").arg(dialog.controller.selectedVersion)
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
            }

            Label {
                Layout.topMargin: 8
                visible: dialog.controller.createsGameFolder
                text: qsTr("Installation folder")
                font.weight: Font.DemiBold
            }

            RowLayout {
                Layout.fillWidth: true
                visible: dialog.controller.createsGameFolder

                TextField {
                    objectName: "installerDirectory"
                    Layout.fillWidth: true
                    text: dialog.controller.directory
                    Accessible.name: qsTr("Installation folder")
                    onTextEdited: dialog.controller.set_directory(text)
                }

                Button {
                    text: qsTr("Browse…")
                    icon.source: Theme.icon("folder")
                    Accessible.name: qsTr("Browse for installation folder")
                    onClicked: picker.open()
                }
            }

            Label {
                Layout.fillWidth: true
                visible: dialog.controller.runnersToInstall.length > 0
                text: qsTr("Lutris will install these runners first: %1")
                        .arg(dialog.controller.runnersToInstall.join(", "))
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
            }

            CheckBox {
                id: desktopShortcut
                objectName: "installerDesktopShortcut"
                visible: dialog.controller.createsShortcuts && dialog.controller.requiredGame.length === 0
                checked: dialog.installation.desktopShortcutDefault
                text: qsTr("Create desktop shortcut")
            }

            CheckBox {
                id: menuShortcut
                objectName: "installerMenuShortcut"
                visible: dialog.controller.createsShortcuts && dialog.controller.requiredGame.length === 0
                checked: dialog.installation.menuShortcutDefault
                text: qsTr("Create application menu shortcut")
            }

            ProgressBar {
                Layout.fillWidth: true
                visible: dialog.controller.loading
                indeterminate: visible
                Accessible.name: qsTr("Looking for installers…")
            }

            Item { Layout.fillHeight: true }
        }

        InstallationPage {
            installation: dialog.installation
        }
    }

    footer: DialogButtonBox {
        Button {
            objectName: "installerBack"
            text: qsTr("Back")
            visible: dialog.controller.selected && !dialog.installation.active
            enabled: !dialog.controller.loading
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.back()
        }

        Button {
            objectName: "installerStart"
            highlighted: true
            text: qsTr("Install")
            visible: dialog.controller.selected && !dialog.installation.active
                     && dialog.controller.requiredGame.length === 0
            enabled: !dialog.controller.loading
                     && (!dialog.controller.createsGameFolder || dialog.controller.directory.trim().length > 0)
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.install(desktopShortcut.checked, menuShortcut.checked)
        }

        Button {
            objectName: "installerCancel"
            text: qsTr("Cancel Installation")
            visible: dialog.installation.running && dialog.installation.stage !== "cancelling"
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: cancelConfirmation.open()
        }

        Button {
            objectName: "installerLaunch"
            highlighted: true
            text: qsTr("Launch")
            visible: dialog.installation.stage === "finished" && dialog.installation.installedGameId.length > 0
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: {
                dialog.installation.launch()
                dialog.close()
            }
        }

        Button {
            objectName: "installerClose"
            text: qsTr("Close")
            visible: !dialog.installation.running
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }
    }
}
