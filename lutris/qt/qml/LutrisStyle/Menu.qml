import QtQuick
import QtQuick.Templates as T

T.Menu {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    margins: 6
    padding: 5
    overlap: 4

    delegate: MenuItem {}

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.animation }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.animation; easing.type: Easing.OutCubic }
        }
    }

    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 80 }
    }

    contentItem: ListView {
        implicitHeight: contentHeight
        implicitWidth: Math.max(220, contentItem.childrenRect.width)
        model: control.contentModel
        interactive: Window.window
                     ? contentHeight + control.topPadding + control.bottomPadding > control.height
                     : false
        clip: true
        currentIndex: control.currentIndex
        boundsBehavior: Flickable.StopAtBounds

        T.ScrollIndicator.vertical: ScrollIndicator {}
    }

    background: Rectangle {
        implicitWidth: 220
        implicitHeight: 40
        radius: Theme.radiusLarge
        color: Theme.raised
        border.color: Theme.borderStrong
    }

    T.Overlay.modal: Rectangle { color: Theme.scrim }
    T.Overlay.modeless: Rectangle { color: "transparent" }
}
