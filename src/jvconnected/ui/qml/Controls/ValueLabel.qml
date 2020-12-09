import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Control {
    id: root
    property string labelText
    property string valueText
    property int orientation: Qt.Horizontal
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
        implicitHeight: orientation == Qt.Horizontal ? Math.max(titleLbl.implicitHeight, valueLbl.implicitHeight) : titleLbl.implicitHeight + valueLbl.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? titleLbl.implicitWidth + valueLbl.implicitWidth : Math.max(titleLbl.implicitWidth, valueLbl.implicitWidth)
        // columns: root.orientation == Qt.Vertical ? 1 : 3
        // rows: root.orientation == Qt.Vertical ? 3 : 1
        Label {
            id: titleLbl
            text: root.labelText
        }
        Item {
            // Layout.fillWidth: root.orientation == Qt.Horizontal ? true : false
        }
        Label {
            id: valueLbl
            text: root.valueText
            // font.family: 'Droid Sans Mono'
            Layout.alignment: root.orientation == Qt.Horizontal ? Layout.AlignVCenter | Layout.AlignRight : Layout.AlignVCenter | Layout.AlignLeft
        }
    }
}
