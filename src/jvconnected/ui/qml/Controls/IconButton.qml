import QtQuick 2.15
import QtQuick.Controls 2.15
import Fonts 1.0

RoundButton {
    id: control

    property bool round: true
    radius: round ? width : 0
    property alias iconName: iconFont.iconName
    property alias pointSize: iconFont.pointSize

    IconFont {
        id: iconFont
    }

    text: iconFont.text
    font: iconFont.iconFont
}
