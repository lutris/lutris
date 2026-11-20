pragma Singleton

import QtQuick

// The colors, metrics and type sizes that the Lutris style and views share
QtObject {
    id: theme

    // The theme preference: "light", "dark", or "default" to follow the desktop
    property string preference: "default"
    // Dark unless the preference or the desktop asks for light; not every platform
    // takes the preference on, so it's followed here too
    readonly property bool dark: preference === "dark"
                                 || preference !== "light" && Application.styleHints.colorScheme !== Qt.ColorScheme.Light

    // Surfaces, from the window back to the popups in front of it
    readonly property color window: dark ? "#131417" : "#f5f5f7"
    readonly property color sidebar: dark ? "#1a1b1f" : "#ebebef"
    readonly property color surface: dark ? "#1f2025" : "#ffffff"
    readonly property color raised: dark ? "#25262c" : "#ffffff"
    readonly property color field: dark ? "#16171a" : "#ffffff"
    readonly property color control: dark ? "#2a2b31" : "#ffffff"
    readonly property color controlHover: dark ? "#33353c" : "#f1f1f4"
    readonly property color controlPressed: dark ? "#3c3e46" : "#e6e6ea"
    readonly property color hover: dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.05)
    readonly property color pressed: dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0, 0, 0, 0.09)
    // The groove of switches and progress bars
    readonly property color track: dark ? "#3a3c44" : "#d3d4db"
    readonly property color border: dark ? "#2d2e35" : "#dcdce2"
    readonly property color borderStrong: dark ? "#3b3d45" : "#c6c7cf"
    readonly property color scrim: Qt.rgba(0, 0, 0, dark ? 0.6 : 0.35)

    // Text and icons
    readonly property color text: dark ? "#ececf0" : "#1c1d21"
    readonly property color textMuted: dark ? "#a2a4ad" : "#5e6069"
    readonly property color textSubtle: dark ? "#6e717b" : "#8d8f98"

    // The Lutris orange, and the states that grow from it
    readonly property color accent: dark ? "#ff8a3d" : "#e2661c"
    readonly property color accentHover: dark ? "#ff9c5a" : "#ec7429"
    readonly property color accentPressed: dark ? "#ec7529" : "#c95714"
    readonly property color accentSubtle: dark ? Qt.rgba(1, 0.54, 0.24, 0.16) : Qt.rgba(0.89, 0.4, 0.11, 0.12)
    readonly property color accentText: dark ? "#ffa66b" : "#c0530f"
    readonly property color textOnAccent: dark ? "#1d1006" : "#ffffff"

    readonly property color danger: dark ? "#f2615d" : "#d33a3a"
    readonly property color dangerHover: dark ? "#f57874" : "#dd4c4c"
    readonly property color warning: dark ? "#f0b546" : "#a8690c"
    readonly property color success: dark ? "#4fc88d" : "#1d9a61"
    readonly property color textOnDanger: "#ffffff"

    // Metrics
    readonly property int radiusSmall: 6
    readonly property int radius: 8
    readonly property int radiusLarge: 12
    readonly property int controlHeight: 34
    readonly property int spacing: 8
    readonly property int animation: 120

    // Type sizes, relative to the desktop's font
    readonly property real fontSize: Application.font.pointSize > 0 ? Application.font.pointSize : 10
    readonly property real smallSize: fontSize * 0.88
    readonly property real largeSize: fontSize * 1.15
    readonly property real titleSize: fontSize * 1.35
    readonly property real headingSize: fontSize * 1.8

    // An icon of the style's icon set
    function icon(name: string): url {
        return name.length > 0 ? Qt.resolvedUrl("icons/" + name + ".svg") : ""
    }
}
