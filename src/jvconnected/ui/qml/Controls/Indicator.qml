import QtQuick 2.14
import QtQuick.Layouts 1.11
import QtQuick.Controls 2.14

Control {
    id: root
    property string labelText
    property int orientation: Qt.Horizontal
    property color activeColor: '#00ff00'
    property color inactiveColor: '#004000'
    property bool valueState: false

    horizontalPadding: 4
    verticalPadding: 4
    implicitWidth: grid.implicitWidth + leftPadding + rightPadding
    implicitHeight: grid.implicitHeight + topPadding + bottomPadding
    font.pointSize: 9

    contentItem: GridLayout {
        id: grid
        // anchors.fill: parent
        columns: root.orientation == Qt.Horizontal ? 3 : 1
        rows: root.orientation == Qt.Horizontal ? 1 : 3
        implicitHeight: orientation == Qt.Horizontal ? Math.max(titleLbl.implicitHeight, indicator.implicitHeight) : titleLbl.implicitHeight + indicator.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? titleLbl.implicitWidth + indicator.implicitWidth : Math.max(titleLbl.implicitWidth, indicator.implicitWidth)
        // columns: root.orientation == Qt.Vertical ? 1 : 3
        // rows: root.orientation == Qt.Vertical ? 3 : 1
        Label {
            id: titleLbl
            text: root.labelText
        }
        Item {
            // Layout.fillWidth: root.orientation == Qt.Horizontal ? true : false
        }
        Rectangle {
            id: indicator
            width: 20
            height: 20
            radius: width / 2
            color: root.valueState ? root.activeColor : root.inactiveColor

        }
    }
}
