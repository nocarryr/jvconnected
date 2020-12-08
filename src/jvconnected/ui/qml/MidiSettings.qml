import QtQuick 2.14
import QtQuick.Layouts 1.11
import QtQuick.Controls 2.14
import Qt.labs.settings 1.0
import DeviceModels 1.0
import MidiModels 1.0
import Controls 1.0

Control {
    id: root

    property EngineModel engine

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

    Control {
        anchors.fill: parent
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
}
