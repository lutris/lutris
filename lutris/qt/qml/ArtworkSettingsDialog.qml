pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "artworkSettingsDialog"

    required property QtObject controller

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(520, parent.width - 32)
    title: qsTr("Artwork Sources")
    modal: true
    closePolicy: controller.working ? Popup.NoAutoClose : Popup.CloseOnEscape

    Connections {
        target: dialog.controller
        function onSaved() { dialog.close() }
    }

    contentItem: ColumnLayout {
        spacing: 8

        Label {
            Layout.fillWidth: true
            text: qsTr("Covers and banners come from each game's store. SteamGridDB fills in what stores don't have, and provides the artwork of games that come from no store.")
            wrapMode: Text.WordWrap
        }

        Label {
            Layout.fillWidth: true
            text: qsTr("SteamGridDB needs your own API key, which you can create from your SteamGridDB account.")
            wrapMode: Text.WordWrap
        }

        Button {
            text: qsTr("Get an API Key…")
            onClicked: dialog.controller.open_key_page()
        }

        Label {
            Layout.fillWidth: true
            text: dialog.controller.keyFromEnvironment
                  ? qsTr("The API key is set by the LUTRIS_STEAMGRIDDB_API_KEY environment variable.")
                  : dialog.controller.keySet ? qsTr("An API key is saved. Enter another to replace it, or clear it.")
                                             : qsTr("No API key is saved, so only store artwork is downloaded.")
            wrapMode: Text.WordWrap
            font.italic: true
        }

        TextField {
            id: key
            objectName: "steamGridDbKey"
            Layout.fillWidth: true
            visible: !dialog.controller.keyFromEnvironment
            enabled: !dialog.controller.working
            echoMode: TextInput.Password
            placeholderText: qsTr("SteamGridDB API key")
            Accessible.name: qsTr("SteamGridDB API key")
        }

        ProgressBar {
            Layout.fillWidth: true
            visible: dialog.controller.working
            indeterminate: visible
            Accessible.name: qsTr("Checking the API key…")
        }
    }

    footer: DialogButtonBox {
        Button {
            text: qsTr("Cancel")
            enabled: !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }

        Button {
            objectName: "clearSteamGridDbKey"
            text: qsTr("Clear Key")
            visible: dialog.controller.keySet && !dialog.controller.keyFromEnvironment
            enabled: !dialog.controller.working
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.save_key("")
        }

        Button {
            objectName: "saveSteamGridDbKey"
            text: qsTr("Save Key")
            visible: !dialog.controller.keyFromEnvironment
            enabled: !dialog.controller.working && key.text.trim().length > 0
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: dialog.controller.save_key(key.text)
        }
    }
}
