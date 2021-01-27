import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0

ColumnLayout {
    id: root

    property CameraModel model

    ValueLabel {
        labelText: 'Value'
        valueText: model.detail.value
        Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
    }
    PlusMinusButtons {
        onPlusClicked: model.detail.increase()
        onMinusClicked: model.detail.decrease()
    }
}
