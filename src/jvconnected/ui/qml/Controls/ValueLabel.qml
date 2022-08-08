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
    property alias valueFont: valueLbl.font

    contentItem: GridLayout {
        id: grid
        // anchors.fill: parent
        columns: root.orientation == Qt.Horizontal ? 3 : 1
        rows: root.orientation == Qt.Horizontal ? 1 : 3
        implicitHeight: root.orientation == Qt.Horizontal ? Math.max(titleLbl.implicitHeight, valueLbl.implicitHeight) : titleLbl.implicitHeight + valueLbl.implicitHeight
        implicitWidth: root.orientation == Qt.Horizontal ? titleLbl.implicitWidth + valueLbl.implicitWidth : Math.max(titleLbl.implicitWidth, valueLbl.implicitWidth)
        // columns: root.orientation == Qt.Vertical ? 1 : 3
        // rows: root.orientation == Qt.Vertical ? 3 : 1
        Label {
            id: titleLbl
            text: root.labelText
            horizontalAlignment: root.orientation == Qt.Horizontal ? Text.AlignLeft : Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            Layout.alignment: root.orientation == Qt.Horizontal ? Layout.AlignVCenter | Layout.AlignLeft : Layout.AlignVCenter | Layout.AlignHCenter
            Layout.fillWidth: root.orientation == Qt.Vertical ? true : false
            Layout.fillHeight: root.orientation == Qt.Horizontal ? true : false
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
        Label {
            id: valueLbl
            text: root.valueText
            color: 'white'
            // font.family: 'Droid Sans Mono'
            font.family: 'monospace'
            horizontalAlignment: root.orientation == Qt.Horizontal ? Text.AlignRight : Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            Layout.alignment: root.orientation == Qt.Horizontal ? Layout.AlignVCenter | Layout.AlignRight : Layout.AlignVCenter | Layout.AlignLeft
            Layout.fillWidth: root.orientation == Qt.Vertical ? true : false
            Layout.fillHeight: root.orientation == Qt.Horizontal ? true : false
        }
    }

    background: Rectangle {
        anchors.fill: parent
        border.color: root.palette.midlight
        border.width: 1
        color: 'transparent'
        radius: 3
    }
}
