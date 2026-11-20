pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import LutrisStyle

Rectangle {
    id: sidebar

    required property QtObject controller

    readonly property string currentTitle: (views.currentItem as SidebarItem)?.viewTitle ?? ""
    readonly property string currentIcon: (views.currentItem as SidebarItem)?.viewIcon ?? "games"

    color: Theme.sidebar

    component SidebarItem: ItemDelegate {
        id: view

        required property int index
        required property string viewTitle
        required property string viewIcon
        required property string runnerName

        objectName: runnerName ? "sidebarRunner_" + runnerName : ""
        width: ListView.view.width - ListView.view.leftMargin - ListView.view.rightMargin
        height: 34
        text: viewTitle
        icon.source: Theme.icon(viewIcon)
        highlighted: ListView.isCurrentItem
        horizontalPadding: 10
        font.weight: highlighted ? Font.DemiBold : Font.Normal
        onClicked: {
            ListView.view.forceActiveFocus()
            sidebar.controller.select_view(index)
        }

        // The accent mark of the current view
        Rectangle {
            x: 0
            anchors.verticalCenter: parent.verticalCenter
            width: 3
            height: view.highlighted ? 16 : 0
            radius: 1.5
            color: Theme.accent

            Behavior on height { NumberAnimation { duration: Theme.animation; easing.type: Easing.OutCubic } }
        }

        TapHandler {
            acceptedButtons: Qt.RightButton
            enabled: view.runnerName.length > 0
            onTapped: runnerMenu.popup()
        }

        Menu {
            id: runnerMenu

            MenuItem {
                objectName: "configureRunner"
                text: qsTr("Configure Runner…")
                icon.source: Theme.icon("configure")
                onTriggered: sidebar.controller.configuration.open_runner(view.runnerName, view.viewTitle)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 16
            Layout.bottomMargin: 10
            spacing: 10

            Image {
                Layout.preferredWidth: 30
                Layout.preferredHeight: 30
                source: sidebar.controller.placeholderArtwork
                sourceSize: Qt.size(60, 60)
                fillMode: Image.PreserveAspectFit
                smooth: true
                Accessible.ignored: true
            }

            Label {
                Layout.fillWidth: true
                text: qsTr("Lutris")
                font.pointSize: Theme.titleSize
                font.weight: Font.Bold
                elide: Text.ElideRight
            }
        }

        ListView {
            id: views
            objectName: "librarySidebar"
            Layout.fillWidth: true
            Layout.fillHeight: true
            leftMargin: 10
            rightMargin: 10
            bottomMargin: 10
            clip: true
            reuseItems: true
            Accessible.name: qsTr("Library views")
            activeFocusOnTab: true
            keyNavigationEnabled: false
            model: sidebar.controller.sidebarModel
            currentIndex: sidebar.controller.sidebarRow
            boundsBehavior: Flickable.StopAtBounds
            spacing: 1

            Keys.onUpPressed: sidebar.controller.select_view(currentIndex - 1)
            Keys.onDownPressed: sidebar.controller.select_view(currentIndex + 1)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                    sidebar.controller.select_view(event.key === Qt.Key_Home ? 0 : count - 1)
                    event.accepted = true
                }
            }

            ScrollBar.vertical: ScrollBar {}

            section.property: "sectionTitle"
            section.delegate: Label {
                required property string section

                width: ListView.view.width - ListView.view.leftMargin - ListView.view.rightMargin
                text: section.toUpperCase()
                leftPadding: 10
                topPadding: 16
                bottomPadding: 6
                font.pointSize: Theme.smallSize * 0.92
                font.weight: Font.DemiBold
                font.letterSpacing: 0.8
                color: Theme.textSubtle
                elide: Text.ElideRight
            }

            delegate: SidebarItem {}
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: Theme.border
        }

        ItemDelegate {
            Layout.fillWidth: true
            Layout.margins: 10
            text: qsTr("Preferences")
            icon.source: Theme.icon("settings")
            onClicked: sidebar.controller.preferences.open_preferences()
        }
    }
}
