import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import DeviceModels 1.0

RowLayout {
    id: root

    property CameraModel model
    property DeviceConfigModel confDevice: model.device.confDevice

    Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
    Indicator {
        orientation: Qt.Vertical
        labelText: 'Online'
        valueState: root.confDevice ? root.confDevice.deviceOnline : false
        activeColor: '#0051ed'
    }
    Indicator {
        orientation: Qt.Vertical
        labelText: 'Active'
        valueState: root.confDevice ? root.confDevice.deviceActive : false
    }
}
