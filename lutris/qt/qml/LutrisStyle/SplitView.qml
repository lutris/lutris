pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Templates as T

T.SplitView {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    // A hairline that grows a grab area on either side of it
    handle: Item {
        id: handle

        implicitWidth: control.orientation === Qt.Horizontal ? 1 : control.width
        implicitHeight: control.orientation === Qt.Horizontal ? control.height : 1

        Rectangle {
            anchors.centerIn: parent
            width: control.orientation === Qt.Horizontal ? (handle.T.SplitHandle.hovered || handle.T.SplitHandle.pressed ? 3 : 1) : parent.width
            height: control.orientation === Qt.Horizontal ? parent.height : (handle.T.SplitHandle.hovered || handle.T.SplitHandle.pressed ? 3 : 1)
            color: handle.T.SplitHandle.pressed ? Theme.accent : handle.T.SplitHandle.hovered ? Theme.borderStrong : Theme.border
        }

        containmentMask: Item {
            x: control.orientation === Qt.Horizontal ? -4 : 0
            y: control.orientation === Qt.Horizontal ? 0 : -4
            width: control.orientation === Qt.Horizontal ? 9 : control.width
            height: control.orientation === Qt.Horizontal ? control.height : 9
        }
    }
}
