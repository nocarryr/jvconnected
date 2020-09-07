import QtQuick 2.14
import QtQuick.Controls 2.14

TabButton {
    id: control

    // width: implicitWidth
    // leftInset: 4
    // rightInset: 4
    leftPadding: 12
    rightPadding: 12

    contentItem: Text {
        // spacing: control.spacing
        // mirrored: control.mirrored
        // display: control.display

        // icon: control.icon
        text: control.text
        font: control.font
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        // color: control.checked ? control.palette.windowText : control.palette.brightText
        color: control.checked ? control.palette.brightText : control.palette.buttonText
    }

    background: Rectangle {
        implicitHeight: 40
        // color: Color.blend(control.checked ? control.palette.window : control.palette.dark,
        //                                      control.palette.mid, control.down ? 0.5 : 0.0)
        color: control.checked ? control.palette.highlight : control.palette.button
        border.color: control.checked ? control.palette.brightText : control.palette.mid
        border.width: 1
        // radius: 6
    }
}
