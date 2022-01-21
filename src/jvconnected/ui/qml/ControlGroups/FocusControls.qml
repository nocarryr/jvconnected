import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import DeviceModels 1.0
import Controls 1.0

ColumnLayout {
    id: root

    property CameraModel model
    property FocusModeModel focusMode: model ? model.focusMode : null
    property FocusPosModel focusPos: model ? model.focusPos : null

    RowLayout {

        Item { Layout.fillWidth: true }
        Label {
            text: 'Mode'
        }


        Button {
            text: 'Push Auto'
            onClicked: { root.focusPos.pushAuto() }
        }

        ComboBox {
            property string currentMode: root.focusMode ? root.focusMode.value : ''
            model: ['AF', 'MF']

            function updateCurrentMode(){
                if (typeof(currentMode) != 'undefined'){
                    currentIndex = indexOfValue(currentMode);
                }
            }

            onCurrentModeChanged: { updateCurrentMode() }

            Component.onCompleted: { updateCurrentMode() }

            onActivated: {
                root.focusMode.setMode(currentText);
                updateCurrentMode();
            }
        }
    }
    RowLayout {
        ShuttleSlider {
            id: focusSlider
            enabled: root.focusMode ? root.focusMode.value == 'MF' : false
            orientation: Qt.Horizontal
            from: -8
            to: 8
            stepSize: 1
            verticalPadding: 10
            snapMode: Slider.SnapAlways
            property bool captured: false

            onPressedChanged: {
                captured = pressed;
                if (!pressed){
                    root.focusPos.stop();
                }
            }

            Connections {
                target: root.focusPos
                function onCurrentSpeedChanged(){
                    if (!focusSlider.captured){
                        focusSlider.value = Qt.binding(function(){ return root.focusPos.currentSpeed; });
                    }
                }
            }

            onValueChanged: {
                if (captured && pressed){
                    if (value < 0){
                        root.focusPos.near(-value);
                    } else {
                        root.focusPos.far(value);
                    }
                }
            }
        }
        Label {
            text: root.focusPos ? root.focusPos.value : ''
        }
    }
}
