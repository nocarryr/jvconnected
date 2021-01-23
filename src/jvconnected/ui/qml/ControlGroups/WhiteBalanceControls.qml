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
            property string currentMode: root.model ? root.model.paint.mode.value : ''

            model: [
                'Faw', 'Preset', 'A', 'B', 'Adjust',
                'WhPaintRP', 'WhPaintRM', 'WhPaintBP', 'WhPaintBM',
                'Awb', '3200K', '5600K', 'Manual',
            ]

            onCurrentModeChanged: { updateCurrentMode() }

            function updateCurrentMode(){
                if (typeof(currentMode) != 'undefined'){
                    currentIndex = indexOfValue(currentMode);
                }
            }

            Component.onCompleted: { updateCurrentMode() }

            onActivated: {
                root.model.paint.mode.setMode(currentText);
                updateCurrentMode();
            }
        }
    }
    ValueLabel {
        labelText: 'Color Temp'
        valueText: root.model ? model.paint.colorTemp.value : ''
    }
}
