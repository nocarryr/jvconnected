import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Controls

ColumnLayout {
    id: root

    property CameraModel model

    ValueLabel {
        labelText: 'Value'
        valueText: model.detail.value
        Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
        valueFont.pointSize: 12
        valueFont.bold: true
    }
    PlusMinusButtons {
        onPlusClicked: model.detail.increase()
        onMinusClicked: model.detail.decrease()
    }
}
