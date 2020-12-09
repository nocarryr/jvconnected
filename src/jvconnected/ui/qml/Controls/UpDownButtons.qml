import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Control {
    id: root
    property int orientation: Qt.Vertical
    property bool autoRepeat: true
    property int autoRepeatDelay: 300
    property int autoRepeatInterval: 200

    signal upClicked()
    signal downClicked()

    contentItem: GridLayout {
        id: grid
        columns: root.orientation == Qt.Vertical ? 1 : 2
        rows: root.orientation == Qt.Vertical ? 2 : 1
        implicitHeight: orientation == Qt.Horizontal ? Math.max(upBtn.implicitHeight, dnBtn.implicitHeight) : upBtn.implicitHeight + dnBtn.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? upBtn.implicitWidth + dnBtn.implicitWidth : Math.max(upBtn.implicitWidth, dnBtn.implicitWidth)

        RoundButton {
            id: upBtn
            text: '\u25b2'
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.upClicked()
        }
        // Item { }
        RoundButton {
            id: dnBtn
            text: '\u25bc'
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.downClicked()
        }
    }
}
