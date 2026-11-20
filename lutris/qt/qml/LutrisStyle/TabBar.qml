import QtQuick
import QtQuick.Templates as T

// Tabs read as a segmented control
T.TabBar {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 3
    spacing: 2

    contentItem: ListView {
        model: control.contentModel
        currentIndex: control.currentIndex

        spacing: control.spacing
        orientation: ListView.Horizontal
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.AutoFlickIfNeeded
        snapMode: ListView.SnapToItem

        highlightMoveDuration: Theme.animation * 1.5
        highlightResizeDuration: Theme.animation * 1.5
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 40
        preferredHighlightEnd: width - 40
        highlight: Rectangle {
            radius: Theme.radiusSmall
            color: Theme.raised
            border.color: Theme.borderStrong
        }
    }

    background: Rectangle {
        radius: Theme.radius
        color: Theme.dark ? Theme.field : Theme.controlPressed
        border.color: Theme.border
    }
}
