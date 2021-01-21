import QtQuick 2.15
import QtQuick.Controls 2.15
import Fonts 1.0

RoundButton {
    id: control

    property bool round: true
    property int direction: Qt.LeftArrow
    radius: round ? width : 0

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
