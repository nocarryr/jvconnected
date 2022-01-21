import QtQuick 2.12
import QtQuick.Controls 2.12

Slider {
    id: control

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + control.availableHeight / 2 - height / 2
        property real centerX: width / 2
        property real handleX: control.visualPosition * width
        property real handleDist: control.value < 0 ? centerX - handleX : handleX - centerX
        implicitWidth: 200
        implicitHeight: 4
        width: control.availableWidth
        height: implicitHeight
        radius: 2
        color: 'transparent'

        Canvas {
            width: parent.width
            height: parent.height

            onWidthChanged: { requestPaint() }
            onHeightChanged: { requestPaint() }
            onPaint: {
                var ctx = getContext('2d'),
                    width = parent.width,
                    centerX = parent.centerX,
                    xPos;

                ctx.clearRect(0, 0, width, height);
                ctx.reset();
                ctx.fillStyle = 'transparent';
                ctx.lineWidth = 1;
                ctx.strokeStyle = '#ffffff';
                ctx.moveTo(centerX, 0);
                ctx.lineTo(centerX, height);
                for (var i=1; i<=8; i++){

                    xPos = centerX + i / 9 * centerX;
                    ctx.moveTo(xPos, 0);
                    ctx.lineTo(xPos, height);

                    xPos = centerX - i / 9 * centerX;
                    ctx.moveTo(xPos, 0);
                    ctx.lineTo(xPos, height);

                }
                ctx.stroke();
            }
        }

        Rectangle {
            x: parent.handleX
            width: control.value < 0 ? parent.handleDist : 0
            height: parent.height
            color: "#21be2b"
            radius: 2
        }
        Rectangle {
            x: parent.centerX
            width: control.value > 0 ? parent.handleDist : 0
            height: parent.height
            color: "#21be2b"
            radius: 2
        }
    }

    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        implicitWidth: 16
        implicitHeight: 16
        radius: 8
        color: control.pressed ? "#f0f0f0" : "#f6f6f6"
        border.color: "#bdbebf"
    }
}
