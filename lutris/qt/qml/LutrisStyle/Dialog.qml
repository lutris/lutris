import QtQuick
import QtQuick.Templates as T

T.Dialog {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding,
                            implicitHeaderWidth,
                            implicitFooterWidth)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding
                             + (implicitHeaderHeight > 0 ? implicitHeaderHeight + spacing : 0)
                             + (implicitFooterHeight > 0 ? implicitFooterHeight + spacing : 0))

    padding: 22
    topPadding: header && header.visible ? 6 : 22
    bottomPadding: footer && footer.visible ? 4 : 22

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: 150; easing.type: Easing.OutCubic }
        }
    }

    background: Rectangle {
        radius: 14
        color: Theme.raised
        border.color: Theme.borderStrong
    }

    header: Label {
        text: control.title
        visible: control.title.length > 0
        elide: Label.ElideRight
        font.pointSize: Theme.titleSize
        font.weight: Font.DemiBold
        leftPadding: 22
        rightPadding: 22
        topPadding: 20
        bottomPadding: 6
    }

    footer: DialogButtonBox {
        visible: count > 0
    }

    T.Overlay.modal: Rectangle {
        color: Theme.scrim
        Behavior on opacity { NumberAnimation { duration: 150 } }
    }

    T.Overlay.modeless: Rectangle { color: "transparent" }
}
