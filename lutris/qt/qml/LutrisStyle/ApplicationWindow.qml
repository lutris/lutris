import QtQuick
import QtQuick.Templates as T

T.ApplicationWindow {
    id: window

    color: Theme.window

    // Anything drawn from the palette, such as text editing menus, matches the theme too
    palette {
        window: Theme.window
        windowText: Theme.text
        base: Theme.field
        alternateBase: Theme.surface
        text: Theme.text
        button: Theme.control
        buttonText: Theme.text
        brightText: Theme.textOnAccent
        highlight: Theme.accent
        highlightedText: Theme.textOnAccent
        accent: Theme.accent
        placeholderText: Theme.textSubtle
        toolTipBase: Theme.raised
        toolTipText: Theme.text
        light: Theme.controlHover
        midlight: Theme.control
        mid: Theme.borderStrong
        dark: Theme.border
        shadow: "black"
        link: Theme.accentText
    }
}
