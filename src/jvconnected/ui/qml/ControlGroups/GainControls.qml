import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0

ColumnLayout {
    id: root

    property CameraModel model

    ValueLabel {
        labelText: 'Mode'
        valueText: root.model ? root.model.gainMode.value : ''
        Layout.fillWidth: true
    }

    RowLayout {

        ValueLabel {
            labelText: 'Value'
            valueText: root.model ? model.gainValue.value : ''
        }

        Item { Layout.fillWidth: true }

        UpDownButtons {
            onUpClicked: root.model.gainValue.increase()
            onDownClicked: root.model.gainValue.decrease()
        }
    }
}
