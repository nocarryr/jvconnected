import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Controls

ColumnLayout {
    id: root

    property CameraModel model

    ColumnLayout {
        Label {
            text: 'Mode'
        }
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
        labelText: ''
        valueText: root.model ? model.paint.colorTemp.value : ''
    }
}
