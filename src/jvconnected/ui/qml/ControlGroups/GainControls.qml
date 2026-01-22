import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Controls

ColumnLayout {
    id: root

    property CameraModel model

    ValueLabel {
        labelText: 'Mode'
        valueText: root.model ? root.model.gainMode.value : ''
        Layout.fillWidth: true
    }

    ValueLabel {
        labelText: 'Value'
        valueText: root.model ? model.gainValue.value : ''
        valueFont.pointSize: 12
        valueFont.bold: true
        Layout.fillWidth: true
    }

    RowLayout {
        Item { Layout.fillWidth: true }
        PlusMinusButtons {
            Layout.alignment: Qt.AlignVCenter || Qt.AlignHCenter
            onPlusClicked: model.gainValue.increase()
            onMinusClicked: model.gainValue.decrease()
        }
        Item { Layout.fillWidth: true }
    }
}
