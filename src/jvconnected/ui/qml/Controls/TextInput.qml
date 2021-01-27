import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Control {
    id: root
    property string labelText
    property alias valueText: txtField.text
    property int orientation: Qt.Horizontal
    horizontalPadding: 4
    verticalPadding: 4
    implicitWidth: grid.implicitWidth + leftPadding + rightPadding
    implicitHeight: grid.implicitHeight + topPadding + bottomPadding
    font.pointSize: 9

    signal submit(string value)

    contentItem: GridLayout {
        id: grid
        // anchors.fill: parent
        columns: root.orientation == Qt.Horizontal ? 3 : 1
        rows: root.orientation == Qt.Horizontal ? 1 : 3
        implicitHeight: root.orientation == Qt.Horizontal ? Math.max(titleLbl.implicitHeight, txtField.implicitHeight) : titleLbl.implicitHeight + txtField.implicitHeight + spacing
        implicitWidth: root.orientation == Qt.Horizontal ? titleLbl.implicitWidth + txtField.implicitWidth + spacing : Math.max(titleLbl.implicitWidth, txtField.implicitWidth)
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
        TextField {
            id: txtField
            font: root.font
            // font.family: 'Droid Sans Mono'
            Layout.alignment: root.orientation == Qt.Horizontal ? Layout.AlignVCenter | Layout.AlignRight : Layout.AlignVCenter | Layout.AlignLeft
            Layout.fillWidth: root.orientation == Qt.Vertical ? true : false
            Layout.fillHeight: root.orientation == Qt.Horizontal ? true : false
            onEditingFinished: {
                root.submit(text);
            }
        }
    }

    background: Rectangle {
        color: 'transparent'
        border.color: root.palette.midlight
        border.width: 1
        radius: 3
    }
}
