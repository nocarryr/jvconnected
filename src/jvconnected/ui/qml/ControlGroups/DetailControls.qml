import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0

RowLayout {
    id: root

    property CameraModel model

    ValueLabel {
        labelText: 'Value'
        valueText: model.detail.value
    }
    LeftRightButtons {
        onRightClicked: model.detail.increase()
        onLeftClicked: model.detail.decrease()
    }
}
