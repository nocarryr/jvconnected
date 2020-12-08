import QtQuick 2.14
import QtQuick.Layouts 1.11
import QtQuick.Controls 2.14
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

MyGroupBox {
    id: root
    title: 'RB Paint'

    property CameraModel model
    property WbRedPaintModel redPaint: model ? model.paint.redPaint : null
    property WbBluePaintModel bluePaint: model ? model.paint.bluePaint : null

    implicitWidth: 200

    content: ColumnLayout {

        Item {
            id: yuvPlane
            width: 100
            height: 100
            property real centerX: x + (width/2)
            property real centerY: y + (height/2)

            property real cursorX: root.bluePaint ? root.bluePaint.rawPos * width / cursorXScale : 0
            property real cursorY: root.redPaint ? ((root.redPaint.rawPos * -1) + cursorYScale) * height / cursorYScale : 0
            property real cursorXScale: root.bluePaint ? root.bluePaint.scale : 64
            property real cursorYScale: root.redPaint ? root.redPaint.scale : 64

            Image {
                anchors.fill: parent
                source: 'qrc:/img/YUV_UV_plane_128x128.png'
                fillMode: Image.PreserveAspectFit
            }

            Rectangle {
                id: cursor
                width: 6
                height: 6
                radius: 3
                border.width: 1
                border.color: 'black'
                color: 'white'

                x: yuvPlane.cursorX - (width/2)
                y: yuvPlane.cursorY - (height/2)

                property real centerX: x + (width/2)
                property real centerY: y + (height/2)
            }

            MouseArea {
                anchors.fill: parent
                preventStealing: true

                function setRBPos(mouse){
                    var bluePos = Math.round(mouse.x / width * yuvPlane.cursorXScale),
                        redPos = Math.round(((mouse.y * -1) + height) / height * yuvPlane.cursorYScale);
                    if (bluePos > 64) {
                        bluePos = 64;
                    } else if (bluePos < 0){
                        bluePos = 0;
                    }
                    if (redPos > 64){
                        redPos = 64;
                    } else if (redPos < 0){
                        redPos = 0;
                    }
                    if (bluePos != root.bluePaint.pos || redPos != root.redPaint.pos){
                        // console.log('setRBPos: ', redPos, bluePos);
                        root.redPaint.setRBPosRaw(redPos, bluePos);
                    }
                }
                onPressed: {
                    setRBPos(mouse);
                    mouse.accepted = true;
                }
                onPositionChanged: {
                    // if (!pressed){
                    //     return;
                    // }
                    if (!containsMouse){
                        return;
                    }
                    setRBPos(mouse);
                    mouse.accepted = true;
                }
                onReleased: {
                    setRBPos(mouse);
                    mouse.accepted = true;
                }
                onPressAndHold: { mouse.accepted = true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            UpDownButtons {
                orientation: Qt.Horizontal
                onUpClicked: {
                    if (root.redPaint){
                        root.redPaint.setRedPos(root.redPaint.pos + 1);
                    }
                }
                onDownClicked: {
                    if (root.redPaint){
                        root.redPaint.setRedPos(root.redPaint.pos - 1);
                    }
                }
            }

            ValueLabel {
                labelText: 'R'
                valueText: root.redPaint ? root.redPaint.value : ''
                orientation: Qt.Horizontal
            }
        }

        RowLayout {
            Layout.fillWidth: true
            LeftRightButtons {
                onLeftClicked: {
                    if (root.bluePaint){
                        root.bluePaint.setBluePos(root.bluePaint.pos - 1);
                    }
                }
                onRightClicked: {
                    if (root.bluePaint){
                        root.bluePaint.setBluePos(root.bluePaint.pos + 1);
                    }
                }
            }

            ValueLabel {
                labelText: 'B'
                valueText: root.bluePaint ? root.bluePaint.value : ''
                orientation: Qt.Horizontal
            }
        }
    }
}
