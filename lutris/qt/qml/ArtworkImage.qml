import QtQuick

Image {
    fillMode: Image.PreserveAspectFit
    sourceSize.width: width * Screen.devicePixelRatio
    sourceSize.height: height * Screen.devicePixelRatio
    asynchronous: true
    Accessible.ignored: true
}
