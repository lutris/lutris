import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs as NativeDialogs
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "storeLoginDialog"

    required property QtObject controller
    readonly property string inputKind: controller.login.inputKind ?? ""
    readonly property bool needsCookies: inputKind === "cookies" || inputKind === "gog"

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(490, parent.width - 32)
    title: qsTr("Sign in to %1").arg(controller.login.name ?? "")
    modal: true
    closePolicy: controller.busy ? Popup.NoAutoClose : Popup.CloseOnEscape

    NativeDialogs.FileDialog {
        id: cookiePicker

        title: qsTr("Select the store’s cookies.txt export")
        nameFilters: [qsTr("Text files (*.txt)"), qsTr("All files (*)")]
        onAccepted: {
            dialog.controller.submit_cookie_file(selectedFile, response.text)
            response.clear()
        }
    }

    contentItem: ColumnLayout {
        spacing: 12

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: {
                switch (dialog.inputKind) {
                case "api_key":
                    return qsTr("Open the browser, create an API key for Lutris, and paste it here.")
                case "epic":
                    return qsTr("Sign in in your browser, then paste the authorization code or the JSON shown by Epic Games.")
                case "cookies":
                    return qsTr("Sign in in your browser. Export only this store’s cookies in Netscape cookies.txt format, then select the file.")
                case "gog":
                    return qsTr("Sign in in your browser and paste the full address from the final page. Export only GOG’s cookies in Netscape cookies.txt format, then select the file.")
                default:
                    return qsTr("Sign in in your browser, then copy the full address from the final page and paste it here.")
                }
            }
        }

        Button {
            objectName: "openStoreBrowser"
            enabled: !dialog.controller.busy
            text: qsTr("Open Browser")
            onClicked: dialog.controller.open_browser()
        }

        TextField {
            id: response
            objectName: "storeLoginResponse"
            Layout.fillWidth: true
            visible: dialog.inputKind !== "cookies"
            enabled: !dialog.controller.busy
            placeholderText: qsTr("Paste sign-in response")
            Accessible.name: placeholderText
            echoMode: TextInput.Password
            onAccepted: if (finish.enabled) finish.clicked()
        }

        Label {
            Layout.fillWidth: true
            visible: text.length > 0
            text: dialog.controller.error
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }

        BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            visible: running
            running: dialog.controller.busy
        }
    }

    footer: DialogButtonBox {
        Button {
            text: qsTr("Cancel")
            enabled: !dialog.controller.busy
            DialogButtonBox.buttonRole: DialogButtonBox.RejectRole
        }

        Button {
            id: finish
            objectName: "finishStoreLogin"

            text: dialog.needsCookies ? qsTr("Select Cookies…") : qsTr("Sign In")
            enabled: !dialog.controller.busy && (dialog.inputKind === "cookies" || response.text.trim().length > 0)
            DialogButtonBox.buttonRole: DialogButtonBox.ActionRole
            onClicked: {
                if (dialog.needsCookies)
                    cookiePicker.open()
                else {
                    dialog.controller.submit(response.text)
                    response.clear()
                }
            }
        }
    }
}
