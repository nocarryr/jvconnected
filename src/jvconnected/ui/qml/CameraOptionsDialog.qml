import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

Dialog {
    id: root
    title: (cameraIndex == -1) ? 'Camera Options' : 'Camera ' + cameraIndex.toString() + ' Options'
    standardButtons: Dialog.Ok | Dialog.Cancel | Dialog.Apply | Dialog.Reset

    property CameraModel deviceModel
    property int cameraIndex: deviceModel ? deviceModel.device.deviceIndex : -1

    MyTabBar {
        id: bar
        width: parent.width

        // MyTabButton { text: 'General'; width: bar.maxItemWidth }
        MyTabButton { text: 'NTP'; width: bar.maxItemWidth }
        // MyTabButton { text: 'Network'; width: bar.maxItemWidth }
    }

    StackLayout {
        id: stack
        currentIndex: bar.currentIndex
        anchors.top: bar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 8

        // Control {
        //     id: generalSettings
        //     deviceModel: root.deviceModel

        //     Connections {
        //         target: root
        //         function onAccepted() { generalSettings.submit() }
        //         function onApplied() { generalSettings.submit() }
        //         function onRejected() { generalSettings.cancel() }
        //         function onReset() { generalSettings.cancel() }
        //     }
        // }

        NTPOptions {
            id: ntpSettings
            deviceModel: root.deviceModel

            Connections {
                target: root
                function onAccepted() { ntpSettings.submit() }
                function onApplied() { ntpSettings.submit() }
                function onRejected() { ntpSettings.cancel() }
                function onReset() { ntpSettings.cancel() }
            }
        }

        // Control {
        //     id: networkSettings
        //     deviceModel: root.deviceModel

        //     Connections {
        //         target: root
        //         function onAccepted() { networkSettings.submit() }
        //         function onApplied() { networkSettings.submit() }
        //         function onRejected() { networkSettings.cancel() }
        //         function onReset() { networkSettings.cancel() }
        //     }
        // }
    }
}
