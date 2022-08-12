import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import DeviceModels 1.0
import Controls 1.0

ColumnLayout {
    id: root

    property CameraModel model
    property MasterBlackPosModel mbPos: model ? model.masterBlackPos : null

    RowLayout {
        ValueLabel {
            labelText: 'Value'
            valueText: root.model ? model.masterBlack.value : ''
            valueFont.pointSize: 12
            valueFont.bold: true
        }

        Item { Layout.fillWidth: true }

        PlusMinusButtons {
            onPlusClicked: root.model.masterBlack.increase()
            onMinusClicked: root.model.masterBlack.decrease()
        }
    }

    ShuttleSlider {
        id: mbSlider
        orientation: Qt.Horizontal
        from: -8
        to: 8
        stepSize: 1
        verticalPadding: 10
        snapMode: Slider.SnapAlways
        property bool captured: false
        Layout.fillWidth: true

        onPressedChanged: {
            captured = pressed;
            if (!pressed){
                root.mbPos.stop();
            }
        }

        Connections {
            target: root.mbPos
            function onCurrentSpeedChanged(){
                if (!mbSlider.captured){
                    mbSlider.value = Qt.binding(function(){ return root.mbPos.currentSpeed; });
                }
            }
        }

        onValueChanged: {
            if (captured && pressed){
                if (value < 0){
                    root.mbPos.down(-value);
                } else {
                    root.mbPos.up(value);
                }
            }
        }
    }
}
