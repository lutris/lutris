pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts
import LutrisStyle

ColumnLayout {
    id: page
    objectName: "installationPage"

    required property QtObject installation

    readonly property string stage: installation.stage
    property var chosenExtras: []

    spacing: 8

    function providerLabel(provider: string): string {
        if (provider === "download")
            return qsTr("Download")
        if (provider === "pga")
            return qsTr("Use Cache")
        return qsTr("Select File")
    }

    NativeDialogs.FileDialog {
        id: filePicker

        property string fileId: ""

        title: qsTr("Choose the installer file")
        onAccepted: page.installation.choose_file(fileId, selectedFile)
    }

    NativeDialogs.FolderDialog {
        id: discPicker
        title: qsTr("Select the folder where the disc is mounted")
        onAccepted: page.installation.choose_disc(selectedFolder)
    }

    NativeDialogs.FileDialog {
        id: runnerFilePicker
        title: page.installation.runnerFileTitle
        onAccepted: page.installation.choose_runner_file(selectedFile)
    }

    Label {
        objectName: "installationStatus"
        Layout.fillWidth: true
        text: page.installation.status
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        font.bold: page.stage === "failed" || page.stage === "finished"
    }

    ProgressBar {
        Layout.fillWidth: true
        visible: page.installation.progressVisible
        indeterminate: page.installation.progress < 0
        value: Math.max(0, page.installation.progress)
        Accessible.name: qsTr("Installation progress")
    }

    Label {
        Layout.fillWidth: true
        visible: page.installation.progressVisible && text.length > 0
        text: page.installation.progressText
        textFormat: Text.PlainText
        elide: Text.ElideRight
    }

    Label {
        Layout.fillWidth: true
        visible: page.stage === "runner_prompt"
        text: page.installation.runnerQuestion
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
    }

    RowLayout {
        visible: page.stage === "runner_prompt"

        Button {
            text: page.installation.runnerFileTitle.length > 0 ? qsTr("Choose File…") : qsTr("Yes")
            onClicked: {
                if (page.installation.runnerFileTitle.length > 0)
                    runnerFilePicker.open()
                else
                    page.installation.answer_runner(true)
            }
        }

        Button {
            text: page.installation.runnerFileTitle.length > 0 ? qsTr("Skip") : qsTr("No")
            onClicked: page.installation.answer_runner(false)
        }
    }

    // Extras
    ListView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: page.stage === "extras"
        clip: true
        model: page.installation.extras

        delegate: CheckDelegate {
            id: extra

            required property var modelData

            width: ListView.view.width
            text: qsTr("%1 (%2)").arg(extra.modelData.label).arg(extra.modelData.source)
            onToggled: {
                const chosen = page.chosenExtras.filter(id => id !== extra.modelData.id)
                if (checked)
                    chosen.push(extra.modelData.id)
                page.chosenExtras = chosen
            }
        }
    }

    Button {
        objectName: "confirmExtras"
        highlighted: true
        visible: page.stage === "extras"
        text: qsTr("Continue")
        onClicked: page.installation.choose_extras(page.chosenExtras)
    }

    // Files and their downloads
    ListView {
        objectName: "installationFiles"
        Layout.fillWidth: true
        Layout.fillHeight: !page.installation.hasLog
        Layout.preferredHeight: contentHeight
        visible: page.stage === "files" || page.stage === "downloading"
        clip: true
        spacing: 6
        model: page.installation.files

        delegate: Frame {
            id: file

            required property var modelData
            readonly property bool choosing: page.stage === "files"

            width: ListView.view.width

            ColumnLayout {
                anchors.fill: parent
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true

                    Label {
                        Layout.fillWidth: true
                        text: file.modelData.label
                        textFormat: Text.PlainText
                        font.bold: true
                        elide: Text.ElideMiddle
                    }

                    Label {
                        visible: file.modelData.details.length > 0
                        text: file.modelData.details
                    }

                    ComboBox {
                        objectName: "fileSource_" + file.modelData.id
                        visible: file.choosing && file.modelData.providers.length > 1
                        model: file.modelData.providers.map(provider => ({ value: provider, text: page.providerLabel(provider) }))
                        textRole: "text"
                        valueRole: "value"
                        Accessible.name: qsTr("Source of %1").arg(file.modelData.label)
                        Component.onCompleted: currentIndex = indexOfValue(file.modelData.provider)
                        onActivated: page.installation.set_file_source(file.modelData.id, currentValue, file.modelData.userPath)
                    }
                }

                Label {
                    Layout.fillWidth: true
                    visible: file.modelData.provider === "user" && file.modelData.hint !== file.modelData.label
                    text: file.modelData.hint
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: file.choosing && file.modelData.provider === "user"

                    TextField {
                        objectName: "filePath_" + file.modelData.id
                        Layout.fillWidth: true
                        text: file.modelData.userPath
                        placeholderText: qsTr("Path to the file")
                        Accessible.name: qsTr("Path of %1").arg(file.modelData.label)
                        onEditingFinished: if (text !== file.modelData.userPath)
                                               page.installation.set_file_source(file.modelData.id, "user", text)
                    }

                    Button {
                        text: qsTr("Browse…")
                        icon.source: Theme.icon("folder")
                        Accessible.name: qsTr("Browse for %1").arg(file.modelData.label)
                        onClicked: {
                            filePicker.fileId = file.modelData.id
                            filePicker.open()
                        }
                    }
                }

                ProgressBar {
                    Layout.fillWidth: true
                    visible: page.stage === "downloading" && (file.modelData.provider === "download"
                             || file.modelData.provider === "steam" && file.modelData.state === "downloading")
                    indeterminate: file.modelData.provider === "steam"
                    value: file.modelData.state === "available" ? 1 : file.modelData.fraction
                    Accessible.name: qsTr("Download of %1").arg(file.modelData.label)
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: progress.text.length > 0 || retry.visible

                    Label {
                        id: progress
                        Layout.fillWidth: true
                        text: file.modelData.error || file.modelData.progressText
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                    }

                    Button {
                        id: retry
                        visible: page.stage === "downloading"
                                 && (file.modelData.state === "failed" || file.modelData.state === "cancelled")
                        text: qsTr("Retry")
                        onClicked: page.installation.retry_file(file.modelData.id)
                    }
                }
            }
        }
    }

    Button {
        objectName: "startInstallationFiles"
        highlighted: true
        visible: page.stage === "files"
        enabled: page.installation.filesReady
        text: qsTr("Install")
        onClicked: page.installation.start_files()
    }

    // A choice the script asks for
    RowLayout {
        Layout.fillWidth: true
        visible: page.stage === "menu"

        ComboBox {
            id: menu
            objectName: "installationMenu"
            Layout.fillWidth: true
            model: page.installation.menuOptions
            textRole: "label"
            valueRole: "id"
            Accessible.name: page.installation.status
            // A new model resets the index, so the preselection follows it
            onModelChanged: currentIndex = page.installation.menuPreselectIndex
        }

        Button {
            objectName: "confirmInstallationMenu"
            highlighted: true
            text: qsTr("Continue")
            enabled: menu.currentIndex >= 0
            onClicked: page.installation.answer_menu(menu.currentValue)
        }
    }

    // A disc the script needs
    RowLayout {
        visible: page.stage === "disc"

        Button {
            text: qsTr("Autodetect")
            onClicked: page.installation.answer_disc("")
        }

        Button {
            text: qsTr("Browse…")
            icon.source: Theme.icon("folder")
            Accessible.name: qsTr("Browse for the disc")
            onClicked: discPicker.open()
        }

        Button {
            visible: page.installation.discCanEject
            text: qsTr("Eject")
            onClicked: page.installation.eject_disc()
        }
    }

    ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: page.installation.hasLog && page.stage !== "files"

        TextArea {
            objectName: "installationLog"
            readOnly: true
            text: page.installation.log
            font.family: "monospace"
            wrapMode: TextEdit.WrapAnywhere
            Accessible.name: qsTr("Installer output")
            onTextChanged: cursorPosition = length
        }
    }

    ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: page.stage === "failed" && page.installation.errorDetails.length > 0

        TextArea {
            readOnly: true
            text: page.installation.errorDetails
            font.family: "monospace"
            wrapMode: TextEdit.WrapAnywhere
            Accessible.name: qsTr("Error details")
        }
    }

    Item {
        Layout.fillHeight: true
        visible: !page.installation.hasLog && page.stage !== "extras" && page.stage !== "files"
                 && page.stage !== "downloading" && !(page.stage === "failed" && page.installation.errorDetails.length > 0)
    }
}
