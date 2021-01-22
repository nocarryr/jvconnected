import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Control {
    id: root
    property int orientation: Qt.Horizontal
    property bool autoRepeat: true
    property int autoRepeatDelay: 300
    property int autoRepeatInterval: 200

    signal leftClicked()
    signal rightClicked()

    contentItem: GridLayout {
        id: grid
        columns: root.orientation == Qt.Vertical ? 1 : 2
        rows: root.orientation == Qt.Vertical ? 2 : 1
        implicitHeight: orientation == Qt.Horizontal ? Math.max(leftBtn.implicitHeight, rightBtn.implicitHeight) : leftBtn.implicitHeight + rightBtn.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? leftBtn.implicitWidth + rightBtn.implicitWidth : Math.max(leftBtn.implicitWidth, rightBtn.implicitWidth)

        ArrowButton {
            id: leftBtn
            direction: Qt.LeftArrow
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.leftClicked()
        }
        // Item { }
        ArrowButton {
            id: rightBtn
            direction: Qt.RightArrow
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.rightClicked()
        }
    }
}
