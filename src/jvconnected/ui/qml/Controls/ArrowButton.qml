import QtQuick
import QtQuick.Controls
import Fonts

RoundButton {
    id: control

    property bool round: true
    property int direction: Qt.LeftArrow
    radius: round ? width : 0
    property alias iconName: iconFont.iconName

    IconFont {
        id: iconFont

        iconName: control.direction == Qt.UpArrow ? "faCaretUp" :
                  control.direction == Qt.DownArrow ? "faCaretDown" :
                  control.direction == Qt.LeftArrow ? "faCaretLeft" :
                  control.direction == Qt.RightArrow ? "faCaretRight": ""
    }

    text: iconFont.text
    font: iconFont.iconFont
}
