import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import MidiModels 1.0
import Controls 1.0

Control {
    id: root

    property EngineModel engine

    signal submit()
    signal cancel()

    InportsModel {
        id: inports
        engine: root.engine
        onPortAdded: {
            var port = arguments[0];
            inportList.addPort(port);
        }
    }
    OutportsModel {
        id: outports
        engine: root.engine
        onPortAdded: {
            var port = arguments[0];
            outportList.addPort(port);
        }
    }

    ListModel {
        id: inportList
        dynamicRoles: true
        property var indexNameMap: ({})
        signal addPort(MidiPortModel port)

        onAddPort: {
            var item = {'name':port.name, 'index':inportList.count};
            indexNameMap[item.index] = port.name;
            inportList.append(item);
        }
    }

    ListModel {
        id: outportList
        dynamicRoles: true
        property var indexNameMap: ({})
        signal addPort(MidiPortModel port)

        onAddPort: {
            var item = {'name':port.name, 'index':outportList.count};
            indexNameMap[item.index] = port.name;
            outportList.append(item);
        }
    }

    MyTabBar {
        id: bar
        width: parent.width

        MyTabButton { text: 'Ports'; width: bar.maxItemWidth }
        MyTabButton { text: 'Mapping'; width: bar.maxItemWidth }
    }

    StackLayout {
        id: stack
        anchors.top: bar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 8
        currentIndex: bar.currentIndex

        Control {
            // anchors.fill: parent
            // Layout.fillWidth: true
            padding: 8

            GroupBox {
                id: inportGroupBox
                title: 'Inputs'
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                width: parent.width / 2
                anchors.rightMargin: 4

                // leftPadding: 0
                // rightPadding: 4

                ListView {
                    id: inportListView
                    anchors.fill: parent
                    model: inportList
                    delegate: CheckBox {
                        property string portName: name
                        property MidiPortModel port: inports.getByName(name)
                        text: port ? port.name : ''
                        checked: port.isActive
                        // onToggled: port.setIsActive(checked)
                        onClicked: { port.setIsActive(!port.isActive) }
                    }
                }
            }
            GroupBox {
                id: outportGroupBox
                title: 'Outputs'
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.left: inportGroupBox.right
                anchors.right: parent.right
                anchors.leftMargin: 4

                // leftPadding: 4
                // rightPadding: 0

                ListView {
                    id: outportListView
                    anchors.fill: parent
                    model: outportList
                    delegate: CheckBox {
                        property string portName: name
                        property MidiPortModel port: outports.getByName(name)
                        text: port ? port.name : ''
                        checked: port.isActive
                        // onToggled: port.setIsActive(checked)
                        onClicked: { port.setIsActive(!port.isActive) }
                    }
                }
            }
        }

        MidiDeviceMapTable {
            id: deviceMapSettings
            engine: root.engine

            Connections {
                target: root
                function onSubmit() { deviceMapSettings.submit() }
                function onCancel() { deviceMapSettings.cancel() }
            }
        }
    }
}
