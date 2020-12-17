import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import NetlinxModels 1.0
import Controls 1.0

Control {
    id: root

    property EngineModel engine
    property bool edited: false
    property string hostaddr: model.hostaddr
    property int hostport: model.hostport

    signal submit()
    signal cancel()

    onSubmit: {
        if (edited) {
            model.setHostaddr(hostaddr);
            model.setHostport(hostport);
        }
        edited = false;
    }

    onCancel: {
        hostaddr = model.hostaddr;
        hostport = model.hostport;
        edited = false;
    }

    NetlinxModel {
        id: model
        engine: root.engine
    }

    contentItem: ColumnLayout {

        Indicator {
            labelText: 'Connected'
            valueState: model.connected
        }

        TextInput {
            id: hostaddrTxt
            labelText: 'Host Address'
            valueText: root.hostaddr ? root.hostaddr : ''
            onSubmit: {
                root.hostaddr = value;
                root.edited = true;
            }
        }
        TextInput {
            id: hostportTxt
            labelText: 'Host Port'
            valueText: root.hostport.toString()
            onSubmit: {
                root.hostport = parseInt(value);
                root.edited = true;
            }
        }

        Item { Layout.fillHeight: true }
    }
}
