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
                Layout.fillWidth: true
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
                Layout.fillWidth: true
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

    RowLayout {
        Label {
            text: 'Presets'
        }
        ColumnLayout {
            id: presetModeBtns
            property bool recordEnabled: false
            IconButton {
                iconName: 'faSave'
                checkable: true
                checked: parent.recordEnabled
                font.pointSize: 9
                Layout.maximumHeight: 16
                padding: 0
                width: height
                backgroundBlendColor: checked ? Qt.rgba(.8,0,0,1) : Qt.rgba(.2,0,0,.8)
                onClicked: { parent.recordEnabled = !parent.recordEnabled }
            }
            IconButton {
                iconName: 'faPlayCircle'
                checkable: true
                checked: !parent.recordEnabled
                font.pointSize: 9
                Layout.maximumHeight: 16
                padding: 0
                width: height
                backgroundBlendColor: checked ? Qt.rgba(0,.8,0,1) : Qt.rgba(0,.2,0,.8)
                onClicked: { parent.recordEnabled = !parent.recordEnabled }

            }
        }
        RowLayout {
            Repeater {
                model: root.zoomPos ? root.zoomPos.presets : []
                RoundButton {
                    text: modelData.name
                    highlighted: modelData.isActive

                    onClicked: {
                        if (presetModeBtns.recordEnabled){
                            root.zoomPos.setPreset(modelData.name);
                            presetModeBtns.recordEnabled = false;
                        } else {
                            root.zoomPos.recallPreset(modelData.name);
                        }
                    }
                }
            }
        }
    }
}
