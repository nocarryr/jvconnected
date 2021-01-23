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
    }

    Item { Layout.fillWidth: true }

    UpDownButtons {
        onUpClicked: root.model.masterBlack.increase()
        onDownClicked: root.model.masterBlack.decrease()
    }
}
