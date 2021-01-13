import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

Control {
    id: root
    property DeviceConfigModel device
    // implicitWidth: contentItem.width
    // implicitHeight: contentItem.height

    property string authUser: ''
    property string authPass: ''
    property int deviceIndex: 0
    property string displayName: ''
    property bool hasChanges: false

    signal setDevice(DeviceConfigModel dev)
    signal submit()
    signal cancel()

    onSetDevice: {
        root.device = dev;
        updateFromDevice();
    }

    onSubmit: { setDeviceValues() }

    onCancel: { updateFromDevice() }

    function updateFromDevice(){
        checkValues();
        device.getValuesFromDevice();
        authUser = device.authUser;
        authPass = device.authPass;
        deviceIndex = device.deviceIndex;
        displayName = device.displayName;
        // hasChanges = false;
        checkValues();
    }

    function setDeviceValues(){
        if (hasChanges){
            device.authUser = root.authUser;
            device.authPass = root.authPass;
            device.deviceIndex = root.deviceIndex;
            device.displayName = root.displayName;
            device.sendValuesToDevice();
            checkValues();
        }
        updateFromDevice();
    }

    function checkValues(){
        hasChanges = (
            authUser != device.authUser || authPass != device.authPass ||
            deviceIndex != device.deviceIndex || device.editedProperties.length > 0 ||
            displayName != device.displayName
        );
    }

    Connections {
        target: device
        function onEditedPropertiesChanged() {
            // root.hasChanges = device.editedProperties.length > 0;
            checkValues();
        }
    }

    contentItem: MyGroupBox {
        title: root.device ? root.device.deviceId : ''

        content: ColumnLayout {
            TextInput {
                labelText: 'Display Name'
                valueText: root.displayName
                onSubmit: {
                    root.displayName = value;
                    root.checkValues();
                }
            }
            TextInput {
                labelText: 'Username'
                valueText: root.authUser
                orientation: Qt.Horizontal
                onSubmit: {
                    root.authUser = value;
                    root.checkValues();
                }
            }
            TextInput {
                labelText: 'Password'
                valueText: root.authPass
                orientation: Qt.Horizontal
                onSubmit: {
                    root.authPass = value;
                    root.checkValues();
                }
            }
            RowLayout {
                ValueLabel {
                    labelText: 'Index'
                    valueText: root.deviceIndex
                    orientation: Qt.Vertical
                }
                UpDownButtons {
                    onDownClicked: {
                        var ix = root.deviceIndex - 1;
                        if (ix < 0){
                            return;
                        }
                        root.deviceIndex = ix;
                        root.checkValues();
                        // root.device.setDeviceIndex(ix);
                    }
                    onUpClicked: {
                        var ix = root.deviceIndex + 1;
                        root.deviceIndex = ix;
                        root.checkValues();
                        // root.device.setDeviceIndex(ix);
                    }
                }
            }
        }
    }
}
