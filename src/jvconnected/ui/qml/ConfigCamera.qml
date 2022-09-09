import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0
import ControlGroups 1.0

Control {
    id: root
    property DeviceConfigModel device
    // implicitWidth: contentItem.width
    // implicitHeight: contentItem.height

    property bool hasChanges: false
    property var formData: {'authUser':'', 'authPass':'', 'hostaddr':'', 'hostport':80, 'deviceIndex':-1, 'displayName':'', 'alwaysConnect':false}
    property var fieldsEdited: []

    signal setDevice(DeviceConfigModel dev)
    signal submit()
    signal cancel()

    onSetDevice: {
        root.device = dev;
        updateFromDevice();
    }

    function setFormField(name, value){
        formData[name] = value;
        if (fieldsEdited.indexOf(name) == -1){
            fieldsEdited.push(name);
        }
        hasChanges = true;
    }

    onSubmit: { setDeviceValues() }

    onCancel: { updateFromDevice() }

    function updateFromDevice(){
        var deviceProps = device.getEditableProperties(),
            deviceValue, formValue, tmp={};
        // console.log('deviceProps: ', JSON.stringify(deviceProps));
        for (const key in deviceProps){
            deviceValue = deviceProps[key];
            tmp[key] = deviceValue;
        }
        root.fieldsEdited = [];
        hasChanges = false;
        root.formData = tmp;
    }

    function setDeviceValues(){
        if (!hasChanges){
            return;
        }
        var data = {};
        for (const key of root.fieldsEdited){
            data[key] = root.formData[key];
        }
        device.setFormValues(data);
        updateFromDevice();
    }

    Connections {
        target: device

        function onPropertiesUpdated(propNames){
            var value, tmp = Object.assign({}, root.formData);
            for (const propName of propNames){
                if (root.fieldsEdited.indexOf(propName) != -1){
                    continue;
                }
                value = device.getEditableProperty(propName);
                // console.log('prop: ', propName, ' = ', value);
                tmp[propName] = value;
            }
            root.formData = tmp;
        }
    }

    contentItem: MyGroupBox {
        title: root.device ? root.device.deviceId : ''

        content: ColumnLayout {
            TextInput {
                labelText: 'Display Name'
                valueText: root.formData['displayName']
                Layout.fillWidth: true
                onSubmit: {
                    root.setFormField('displayName', value);
                }
            }
            GridLayout {
                columns: 2
                Layout.fillWidth: true
                TextInput {
                    labelText: 'Username'
                    valueText: root.formData['authUser']
                    Layout.fillWidth: true
                    onSubmit: {
                        root.setFormField('authUser', value);
                    }
                }
                TextInput {
                    labelText: 'Password'
                    valueText: root.formData['authPass']
                    Layout.fillWidth: true
                    onSubmit: {
                        root.setFormField('authPass', value);
                    }
                }
                TextInput {
                    labelText: 'IP Address'
                    valueText: root.formData['hostaddr']
                    Layout.fillWidth: true
                    onSubmit: {
                        root.setFormField('hostaddr', value);
                    }
                }
                TextInput {
                    labelText: 'Port'
                    valueText: root.formData['hostport'].toString()
                    Layout.fillWidth: true
                    onSubmit: {
                        root.setFormField('hostport', parseInt(value));
                    }
                }
            }
            RowLayout {
                Label {
                    text: 'Always Connect'
                }
                Switch {
                    id: alwaysConnectSwitch
                    checked: root.formData['alwaysConnect']
                    onToggled: { root.setFormField('alwaysConnect', checked) }
                }
            }
            RowLayout {
                ColumnLayout {
                    ConnectionIndicator {
                        state: root.device ? root.device.connectionState : 'unknown'
                    }
                    RowLayout {
                        Label {
                            text: root.device ? root.device.connectionState : ''
                        }
                        Button {
                            text: 'Reconnect'
                            onClicked: { root.device.reconnect() }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                RowLayout {
                    Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                    ValueLabel {
                        labelText: 'Index'
                        valueText: root.formData['deviceIndex'] != -1 ? root.formData['deviceIndex'].toString() : ''
                        orientation: Qt.Vertical
                    }
                    UpDownButtons {
                        onDownClicked: {
                            var ix = root.formData['deviceIndex'];
                            if (ix == -1){
                                root.setFormField('deviceIndex', 0)
                                return;
                            }
                            ix -= 1;
                            if (ix < 0){
                                return;
                            }
                            root.setFormField('deviceIndex', ix);
                        }
                        onUpClicked: {
                            var ix = root.formData['deviceIndex'];
                            if (ix == -1){
                                root.setFormField('deviceIndex', 0)
                                return;
                            }
                            ix += 1;
                            root.setFormField('deviceIndex', ix);
                        }
                    }
                }
            }
        }
    }
}
