import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import DeviceModels 1.0
import Controls 1.0

ColumnLayout {
    id: root

    property CameraModel model
    property ZoomPosModel zoomPos: model ? model.zoomPos : null

    RowLayout {
        RowLayout {
            ShuttleSlider {
                id: speedSlider
                orientation: Qt.Horizontal
                from: -8
                to: 8
                stepSize: 1
                snapMode: Slider.SnapAlways
                property bool captured: false

                onPressedChanged: {
                    captured = pressed;
                    if (!pressed){
                        root.zoomPos.stop();
                    }
                }

                Connections {
                    target: root.zoomPos
                    function onCurrentSpeedChanged(){
                        if (!speedSlider.captured){
                            speedSlider.value = Qt.binding(function(){ return root.zoomPos.currentSpeed; });
                        }
                    }
                }

                onValueChanged: {
                    if (captured && pressed){
                        if (value < 0){
                            root.zoomPos.wide(-value);
                        } else {
                            root.zoomPos.tele(value);
                        }
                    }
                }
            }
            ProgressBar {
                id: posSlider
                from: 0
                to: 499
                value: root.zoomPos ? root.zoomPos.pos : 0
            }
        }
        Item { Layout.fillWidth: true }
        Label {
            text: root.zoomPos ? root.zoomPos.value : ''
            font.pointSize: 12
            font.bold: true
            color: 'white'
        }
    }
}
