import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0

ApplicationWindow {
    id: window
    visible: true
    property alias running: engine.running

    Component.onCompleted: {
        engine.open();
    }
    palette: paletteManager.currentPalette

    width: 800
    height: 600

    Settings {
        property alias x: window.x
        property alias y: window.y
        property alias width: window.width
        property alias height: window.height
    }

    menuBar: MenuBar {
        Menu {
            title: qsTr("&File")
            Action {
                text: qsTr("&Settings")
                onTriggered: settingsWindow.open()
            }
            MenuSeparator { }
            Action {
                text: qsTr("&Quit")
                onTriggered: Qt.quit()
            }
        }
    }

    header: ToolBar {
        id: toolBar
        contentItem: RowLayout {
            anchors.fill: parent
            Item { Layout.fillWidth: true }
            ToolButton {
                text: 'Start'
                enabled: !window.running
                onClicked: engine.open()
            }
            ToolSeparator { }
            ToolButton {
                text: 'Stop'
                enabled: window.running
                onClicked: engine.close()
                Layout.rightMargin: 12
            }
        }
    }

    EngineModel {
        id: engine

    }

    ListModel {
        id: deviceListModel
        dynamicRoles: true
        property alias deviceViewIndices: engine.deviceViewIndices
        property var modelIndices: []

        onDeviceViewIndicesChanged: {
            resortIndices();
        }


        function resortIndices(){
            var dev, devId, devIdx, insertData, itemData, item;
            for (var i=0;i<deviceViewIndices.length;i++){
                devId = deviceViewIndices[i];
                dev = engine.getDevice(devId);
                devIdx = dev.deviceIndex;
                itemData = getById(devId);

                if (itemData === null){
                    item = {'deviceId':devId, 'deviceIndex':devIdx};
                    insertData = findInsertIndex(devIdx);
                    if (insertData.insert){
                        item.viewIndex = insertData.index;
                        // deviceListModel.append({'deviceId':devId, 'deviceIndex':devIdx})
                        deviceListModel.insert(insertData.index, item);
                    } else {
                        item.viewIndex = count;
                        deviceListModel.append(item);
                    }
                } else if (itemData.index != i) {
                    item = itemData.item;
                    deviceListModel.move(itemData.index, i, 1);
                    deviceListModel.setProperty(i, 'viewIndex', i);
                }
            }
        }

        function getById(devId){
            var item;
            for (var i=0;i<count;i++){
                item = deviceListModel.get(i);
                if (item.deviceId == devId){
                    return {'item':item, 'index':i};
                }
            }
            return null;
        }
        function findInsertIndex(devIdx){
            var item;
            for (var i=0;i<count;i++){
                item = deviceListModel.get(i);
                if (item.deviceIndex >= devIdx){
                    return {'index':i, 'insert':true};
                }
            }
            return {'index':count, 'insert':false};
        }
    }

    StackView {
        id: mainView
        anchors.fill: parent
        ScrollView {
            anchors.fill: parent
            Row {
                id: cameraContainer
                spacing: 8

                move: Transition {
                    NumberAnimation { properties: "x,y"; duration: 400; easing.type: Easing.OutCubic }
                }

                Repeater {
                    model: deviceListModel

                    delegate: Camera {
                        property string devId: deviceId

                        Component.onCompleted: {
                            device = Qt.binding(function(){ return engine.getDevice(devId) });
                        }
                    }
                }
            }
        }
    }
    SettingsWindow {
        id: settingsWindow
        engine: engine
        width: 800
        height: 600
        visible: false
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
    }
}
