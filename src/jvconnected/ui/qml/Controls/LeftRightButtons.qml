import QtQuick 2.14
import QtQuick.Layouts 1.11
import QtQuick.Controls 2.14

Control {
    id: root
    property int orientation: Qt.Horizontal
    property bool autoRepeat: true
    property int autoRepeatDelay: 300
    property int autoRepeatInterval: 200

    signal leftClicked()
    signal rightClicked()

    implicitWidth: grid.implicitWidth + leftPadding + rightPadding
    implicitHeight: grid.implicitHeight + topPadding + bottomPadding

    GridLayout {
        id: grid
        columns: root.orientation == Qt.Vertical ? 1 : 2
        rows: root.orientation == Qt.Vertical ? 2 : 1
        implicitHeight: orientation == Qt.Horizontal ? Math.max(leftBtn.implicitHeight, rightBtn.implicitHeight) : leftBtn.implicitHeight + rightBtn.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? leftBtn.implicitWidth + rightBtn.implicitWidth : Math.max(leftBtn.implicitWidth, rightBtn.implicitWidth)

        RoundButton {
            id: leftBtn
            text: '\u25c0'
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.leftClicked()
        }
        // Item { }
        RoundButton {
            id: rightBtn
            text: '\u25b6'
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.rightClicked()
        }
    }
}
