import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Control {
    id: root
    property string labelText
    property int orientation: Qt.Horizontal
    property color activeColor: '#00ff00'
    property color inactiveColor: '#004000'
    property bool valueState: false
    implicitWidth: grid.implicitWidth + leftPadding + rightPadding
    implicitHeight: grid.implicitHeight + topPadding + bottomPadding

    horizontalPadding: 4
    verticalPadding: 4
    font.pointSize: 9

    contentItem: GridLayout {
        id: grid
        // anchors.fill: parent
        columns: root.orientation == Qt.Horizontal ? 3 : 1
        rows: root.orientation == Qt.Horizontal ? 1 : 3
        implicitHeight: root.orientation == Qt.Horizontal ? Math.max(titleLbl.implicitHeight, indicator.implicitHeight) : titleLbl.implicitHeight + indicator.implicitHeight + spacing
        implicitWidth: root.orientation == Qt.Horizontal ? titleLbl.implicitWidth + indicator.implicitWidth + spacing : Math.max(titleLbl.implicitWidth, indicator.implicitWidth)
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
        Item {
            id: indicator
            implicitWidth: 20
            implicitHeight: 20
            Layout.fillWidth: root.orientation == Qt.Vertical ? true : false
            Layout.fillHeight: root.orientation == Qt.Horizontal ? true : false
            Rectangle {
                anchors.centerIn: parent
                width: 20
                height: 20
                radius: width / 2
                color: root.valueState ? root.activeColor : root.inactiveColor
                Layout.alignment: root.orientation == Qt.Horizontal ? Layout.AlignVCenter | Layout.AlignRight : Layout.AlignVCenter | Layout.AlignHCenter
            }
        }
    }

    background: Rectangle {
        border.color: root.palette.midlight
        border.width: 1
        radius: 3
    }
}
