import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window

    required property QtObject controller
    required property QtObject prompts

    title: qsTr("Lutris")
    width: 1100
    height: 700
    minimumWidth: 640
    minimumHeight: 420

    menuBar: MenuBar {
        Menu {
            title: qsTr("Library")

            MenuItem {
                objectName: "addLocalGame"
                text: qsTr("Add Locally Installed Game…")
                onTriggered: window.controller.localGames.open_registration("", "")
            }
        }
    }

    header: LibraryToolbar { controller: window.controller }

    LibraryView {
        anchors.fill: parent
        controller: window.controller
    }

    PromptHost { prompts: window.prompts }

    Connections {
        target: window.controller.localGames
        function onRequested() { localGameLoader.active = true }
    }

    Loader {
        id: localGameLoader
        active: false
        sourceComponent: LocalGameDialog {
            controller: window.controller.localGames
            onClosed: localGameLoader.active = false
        }
        onLoaded: if (status === Loader.Ready) (item as LocalGameDialog).open()
    }

    Connections {
        target: window.controller.installers
        function onRequested() { installerLoader.active = true }
    }

    Loader {
        id: installerLoader
        active: false
        sourceComponent: InstallerDialog {
            controller: window.controller.installers
            onClosed: {
                controller.close_installers()
                installerLoader.active = false
            }
        }
        onLoaded: if (status === Loader.Ready) (item as InstallerDialog).open()
    }

    footer: ToolBar {
        visible: window.controller.statusText.length > 0
        implicitHeight: visible ? statusLabel.implicitHeight + 14 : 0

        Label {
            id: statusLabel
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 12
            text: window.controller.statusText
            Accessible.role: Accessible.StatusBar
        }
    }
}
