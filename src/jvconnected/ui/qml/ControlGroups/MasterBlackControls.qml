import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0

RowLayout {
    id: root

    property CameraModel model

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
