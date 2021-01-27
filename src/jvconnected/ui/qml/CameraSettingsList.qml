import QtQuick 2.14
import QtQuick.Layouts 1.11
import QtQuick.Controls 2.14
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

Control {
    id: root

    property EngineModel engine

    signal submit()
    signal cancel()


    ListModel {
        id: confList
        dynamicRoles: true

        property var deviceIds: []
        signal addDevice(DeviceConfigModel device)

        onAddDevice: {
            var i = deviceIds.indexOf(device.deviceId);
            if (i != -1){
                return;
            }
            i = confList.count;
            var item = {'deviceId':device.deviceId, 'viewIndex':i, 'edited':false};
            confList.append(item);
        }
    }

    Connections {
        target: engine
        function onConfigDeviceAdded(device) {
            confList.addDevice(device);
        }
    }


    ListView {
        id: confListView
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: parent.width / 2

        property real maxItemWidth: 20
        // contentWidth: maxItemWidth

        model: confList
        delegate: Label {
            id: confListItem
            text: device ? device.displayName : deviceId
            font.italic: edited
            font.bold: edited
            padding: 4

            property string localDeviceId: deviceId
            property DeviceConfigModel device

            Component.onCompleted: {
                confListItem.device = engine.getDeviceConfig(confListItem.localDeviceId);
            }

            onWidthChanged: {
                if (width > confListView.maxItemWidth){
                    confListView.maxItemWidth = width;
                }
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                hoverEnabled: false
                onClicked: {
                    confListView.currentIndex = viewIndex;
                }
            }
        }
        highlight: Rectangle {
            color: root.palette.highlight
            opacity: .5
            radius: 5
            border.color: Qt.darker(root.palette.text, 1.2)
        }
        focus: true

        onCurrentIndexChanged: {
            cameraFormStack.currentIndex = currentIndex;
        }
    }
    StackLayout {
        id: cameraFormStack
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: confListView.right
        anchors.right: parent.right

        Repeater {
            id: cameraFormRepeater
            model: confList

            delegate: ConfigCamera {
                Connections {
                    target: root
                    function onSubmit() { submit() }
                    function onCancel() { cancel() }
                }

                onHasChangesChanged: {
                    // console.log('hasChanges=', hasChanges, ': ', deviceId);
                    confList.setProperty(index, 'edited', hasChanges);
                }

                Component.onCompleted: {
                    var dev = engine.getDeviceConfig(deviceId);
                    setDevice(dev);
                }
            }
        }
    }
}
