import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Controls
import DeviceModels

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
