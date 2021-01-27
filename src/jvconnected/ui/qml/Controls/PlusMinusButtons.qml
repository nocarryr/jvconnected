import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Fonts 1.0

Control {
    id: root
    property int orientation: Qt.Horizontal
    property bool autoRepeat: true
    property int autoRepeatDelay: 300
    property int autoRepeatInterval: 200
    property IconFont iconFont: IconFont { pointSize: 12 }

    signal plusClicked()
    signal minusClicked()

    contentItem: GridLayout {
        id: grid
        columns: root.orientation == Qt.Vertical ? 1 : 2
        rows: root.orientation == Qt.Vertical ? 2 : 1
        implicitHeight: orientation == Qt.Horizontal ? Math.max(leftBtn.implicitHeight, rightBtn.implicitHeight) : leftBtn.implicitHeight + rightBtn.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? leftBtn.implicitWidth + rightBtn.implicitWidth : Math.max(leftBtn.implicitWidth, rightBtn.implicitWidth)

        RoundButton {
            id: leftBtn
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.minusClicked()
            property IconFont iconFont: IconFont { iconName: 'faMinus' }
            text: iconFont.text
            font: root.iconFont.iconFont
        }
        // Item { }
        RoundButton {
            id: rightBtn
            autoRepeat: root.autoRepeat
            autoRepeatDelay: root.autoRepeatDelay
            autoRepeatInterval: root.autoRepeatInterval
            onClicked: root.plusClicked()
            property IconFont iconFont: IconFont { iconName: 'faPlus' }
            text: iconFont.text
            font: root.iconFont.iconFont
        }
    }
}
