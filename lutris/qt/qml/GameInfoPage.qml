pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// The game's own details on its configuration form
ScrollView {
    id: page
    objectName: "gameInfoPage"

    required property QtObject controller
    readonly property var game: controller.game

    contentWidth: availableWidth

    Dialog {
        id: confirmRunner
        objectName: "confirmRunnerChange"

        property string runner: ""

        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: qsTr("Confirm runner change")
        standardButtons: Dialog.Yes | Dialog.No

        Label {
            width: Math.min(420, page.width)
            text: qsTr("Are you sure you want to change the runner for this game? This will reset the full configuration for this game and is not reversible.")
            wrapMode: Text.WordWrap
        }

        onAccepted: page.controller.set_runner(runner)
        onRejected: runnerBox.currentIndex = runnerBox.indexOfValue(page.game.runner ?? "")
    }

    GridLayout {
        width: page.availableWidth
        columns: 2
        columnSpacing: 12
        rowSpacing: 8

        Label { text: qsTr("Name") }
        TextField {
            objectName: "gameInfoName"
            Layout.fillWidth: true
            text: page.game.name ?? ""
            Accessible.name: qsTr("Name")
            onEditingFinished: page.controller.set_detail("name", text)
        }

        Label { text: qsTr("Sort name") }
        TextField {
            Layout.fillWidth: true
            text: page.game.sortname ?? ""
            placeholderText: qsTr("Sorted by its name")
            Accessible.name: qsTr("Sort name")
            onEditingFinished: page.controller.set_detail("sortname", text)
        }

        Label { text: qsTr("Runner") }
        ComboBox {
            id: runnerBox
            objectName: "gameInfoRunner"
            Layout.fillWidth: true
            model: page.controller.runnerChoices
            textRole: "label"
            valueRole: "value"
            Accessible.name: qsTr("Runner")
            onModelChanged: currentIndex = indexOfValue(page.game.runner ?? "")
            onActivated: {
                if (currentValue === page.game.runner)
                    return
                if (page.game.runner && !page.controller.isNewGame) {
                    confirmRunner.runner = currentValue
                    confirmRunner.open()
                } else {
                    page.controller.set_runner(currentValue)
                }
            }

            Connections {
                target: page.controller
                function onStateChanged() { runnerBox.currentIndex = runnerBox.indexOfValue(page.game.runner ?? "") }
            }
        }

        Label { text: qsTr("Release year") }
        TextField {
            Layout.preferredWidth: 120
            text: page.game.year ?? ""
            inputMethodHints: Qt.ImhDigitsOnly
            validator: IntValidator { bottom: 0; top: 9999 }
            Accessible.name: qsTr("Release year")
            onEditingFinished: page.controller.set_detail("year", text)
        }

        Label { text: qsTr("Playtime") }
        TextField {
            Layout.fillWidth: true
            text: page.game.playtime ?? ""
            placeholderText: qsTr("Such as 2 hours 30 minutes")
            Accessible.name: qsTr("Playtime")
            onEditingFinished: page.controller.set_detail("playtime", text)
        }

        Label { text: qsTr("Identifier") }
        TextField {
            Layout.fillWidth: true
            text: page.game.slug ?? ""
            placeholderText: qsTr("Made from the name")
            Accessible.name: qsTr("Identifier")
            onEditingFinished: page.controller.set_detail("slug", text)
        }

        Label {
            visible: (page.game.directory ?? "").length > 0
            text: qsTr("Directory")
        }
        Label {
            Layout.fillWidth: true
            visible: (page.game.directory ?? "").length > 0
            text: page.game.directory ?? ""
            textFormat: Text.PlainText
            elide: Text.ElideMiddle
        }

        Label {
            visible: (page.game.configPath ?? "").length > 0
            text: qsTr("Game config")
        }
        Label {
            Layout.fillWidth: true
            visible: (page.game.configPath ?? "").length > 0
            text: page.game.configPath ?? ""
            textFormat: Text.PlainText
            elide: Text.ElideMiddle
        }
    }
}
