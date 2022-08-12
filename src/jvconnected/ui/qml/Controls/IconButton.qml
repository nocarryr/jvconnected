import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Controls.impl 2.12
import QtQuick.Templates 2.12 as T
import Fonts 1.0

RoundButton {
    id: control

    property bool round: true
    radius: round ? width : 0
    property alias iconName: iconFont.iconName
    property alias pointSize: iconFont.pointSize
    property alias backgroundBlendColor: background.blendColor
    property alias textBlendColor: contentItem.blendColor

    IconFont {
        id: iconFont
    }

    text: iconFont.text
    font: iconFont.iconFont

    contentItem: IconLabel {
        id: contentItem
        spacing: control.spacing
        mirrored: control.mirrored
        display: control.display
        property color defaultColor: control.checked || control.highlighted ? control.palette.brightText :
               control.flat && !control.down ? (control.visualFocus ? control.palette.highlight : control.palette.windowText) : control.palette.buttonText
        property color blendColor: '#00000000'
        color: Qt.tint(defaultColor, blendColor)

        icon: control.icon
        text: control.text
        font: control.font
    }

    background: Rectangle {
        id: background
        implicitWidth: 40
        implicitHeight: 40
        radius: control.radius
        opacity: enabled ? 1 : 0.3
        visible: !control.flat || control.down || control.checked || control.highlighted
        property color defaultColor: Color.blend(control.checked || control.highlighted ? control.palette.dark : control.palette.button,
                                                                    control.palette.mid, control.down ? 0.5 : 0.0)
        property color blendColor: '#00000000'
        color: Qt.tint(defaultColor, blendColor)
        border.color: control.palette.highlight
        border.width: control.visualFocus ? 2 : 0
    }
}
