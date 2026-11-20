import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T

T.BusyIndicator {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset,
                            implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset,
                             implicitContentHeight + topPadding + bottomPadding)

    padding: 4

    contentItem: Item {
        implicitWidth: 28
        implicitHeight: 28
        opacity: control.running ? 1 : 0

        Behavior on opacity { NumberAnimation { duration: 200 } }

        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: "transparent"
            border.width: 3
            border.color: Theme.track
        }

        Shape {
            id: arc
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: Theme.accent
                strokeWidth: 3
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap

                PathAngleArc {
                    centerX: arc.width / 2
                    centerY: arc.height / 2
                    radiusX: arc.width / 2 - 1.5
                    radiusY: arc.height / 2 - 1.5
                    startAngle: -90
                    sweepAngle: 100
                }
            }

            RotationAnimator on rotation {
                running: control.running && control.visible
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 900
            }
        }
    }
}
