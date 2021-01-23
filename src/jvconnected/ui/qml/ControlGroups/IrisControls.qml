import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0

ColumnLayout {
    id: root

    property CameraModel model

    RowLayout {

        Label {
            text: 'Mode'
        }

        Item { }

        ComboBox {
            property string currentMode: root.model ? root.model.iris.mode : ''
            model: ['Auto', 'Manual']

            function updateCurrentMode(){
                if (typeof(currentMode) != 'undefined'){
                    currentIndex = indexOfValue(currentMode);
                }
            }

            onCurrentModeChanged: { updateCurrentMode() }

            Component.onCompleted: { updateCurrentMode() }

            onActivated: {
                var modeBool = true ? currentText == 'Auto' : false
                root.model.iris.setAutoIris(modeBool);
                updateCurrentMode();
            }
        }
    }

    RowLayout {

        ValueLabel {
            labelText: 'F-Stop'
            valueText: root.model ? root.model.iris.fstop : ''
            orientation: Qt.Vertical
        }

        Item { Layout.fillWidth: true }

        LeftRightButtons {
            enabled: root.model ? model.iris.mode == 'Manual' : false
            onRightClicked: root.model.iris.increase()
            onLeftClicked: root.model.iris.decrease()
        }

        Slider {
            enabled: root.model ? root.model.iris.mode == 'Manual' : false
            orientation: Qt.Horizontal
            from: 0
            to: 255
            stepSize: 1
            snapMode: Slider.SnapAlways
            property real irisValue: root.model ? root.model.iris.pos : 0
            property bool captured: false
            onIrisValueChanged: {
                if (!captured){
                    value = irisValue;
                }
            }
            onPressedChanged: {
                captured = pressed;
            }
            onValueChanged: {
                if (captured && pressed){
                    root.model.iris.setPos(value);
                }
            }
        }
    }
}
