import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Frame {
    id: root
    topPadding: 8
    bottomPadding: 8
    leftPadding: 0
    rightPadding: 0
    property Item control

    // property alias text: lbl.text
    property string text
    property alias horizontalAlignment: lbl.horizontalAlignment
    property alias backgroundColor: bgRect.color
    property alias textColor: lbl.color

    font.pointSize: 10

    background: Rectangle {
        id: bgRect
        border.color: palette.dark
        color: palette.alternateBase
        radius: 2
    }

    contentItem: Label {
        id: lbl
        text: root.text
        verticalAlignment: Qt.AlignVCenter
        horizontalAlignment: Qt.AlignHCenter
        font: root.font
    }
}
