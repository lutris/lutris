import QtQuick
import QtQuick.Controls

Pane {
    id: sidebar

    required property QtObject controller
    padding: 6

    ListView {
        id: views
        objectName: "librarySidebar"
        anchors.fill: parent
        clip: true
        reuseItems: true
        Accessible.name: qsTr("Library views")
        activeFocusOnTab: true
        keyNavigationEnabled: false
        model: sidebar.controller.sidebarModel
        currentIndex: sidebar.controller.sidebarRow
        boundsBehavior: Flickable.StopAtBounds

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
            width: ListView.view.width
            text: section
            leftPadding: 8
            topPadding: 13
            bottomPadding: 3
            font.bold: true
        }

        delegate: ItemDelegate {
            required property int index
            required property string viewTitle
            width: views.width - 8
            text: viewTitle
            highlighted: views.currentIndex === index
            onClicked: {
                views.forceActiveFocus()
                sidebar.controller.select_view(index)
            }
        }
    }
}
