import QtQuick 2.14
import QtQuick.Layouts 1.11
import QtQuick.Controls 2.14

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
        implicitHeight: orientation == Qt.Horizontal ? Math.max(titleLbl.implicitHeight, txtField.implicitHeight) : titleLbl.implicitHeight + txtField.implicitHeight
        implicitWidth: orientation == Qt.Horizontal ? titleLbl.implicitWidth + txtField.implicitWidth : Math.max(titleLbl.implicitWidth, txtField.implicitWidth)
        // columns: root.orientation == Qt.Vertical ? 1 : 3
        // rows: root.orientation == Qt.Vertical ? 3 : 1
        Label {
            id: titleLbl
            text: root.labelText
        }
        Item {
            // Layout.fillWidth: root.orientation == Qt.Horizontal ? true : false
        }
        TextField {
            id: txtField
            font: root.font
            // font.family: 'Droid Sans Mono'
            Layout.alignment: root.orientation == Qt.Horizontal ? Layout.AlignVCenter | Layout.AlignRight : Layout.AlignVCenter | Layout.AlignLeft
            onEditingFinished: {
                root.submit(text);
            }
        }
    }
}
