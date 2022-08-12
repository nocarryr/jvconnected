import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import DeviceModels 1.0
import Controls 1.0

Control {
    id: root

    property string address
    property bool hasChanges: false
    property var changedProps: []
    property CameraModel deviceModel
    property NTPParamsModel paramsModel: deviceModel.ntpParams

    signal submit()
    signal cancel()

    horizontalPadding: 20
    topPadding: 10
    bottomPadding: 30

    onParamsModelChanged: {
        if (root.paramsModel) {
            updateFromModel();
        }
    }

    onSubmit: { applyChanges() }

    onCancel: { updateFromModel() }

    function updateFromModel(){
        address = root.paramsModel.address;
        hasChanges = false;
        changedProps = [];
    }

    function applyChanges(){
        if (hasChanges) {
            for (const prop of changedProps){
                if (prop == 'address'){
                    root.paramsModel.setAddress(root.address);
                }
            }
        }
        hasChanges = false;
        changedProps = [];
    }

    Connections {
        target: root.paramsModel
        function onAddressChanged(){
            if (!root.changedProps.includes('address')){
                root.address = root.paramsModel.address;
            }
        }
    }

    contentItem: GridLayout {
        id: grid
        property real cellWidth: 120
        columns: 2
        ValueLabel {
            labelText: 'Address'
            valueText: root.paramsModel ? root.paramsModel.address : ''
            Layout.columnSpan: 2
            Layout.alignment: Qt.AlignHCenter || Qt.AlignTop
            Layout.preferredWidth: grid.cellWidth * 2
        }
        Indicator {
            labelText: 'Syncronized'
            valueState: root.paramsModel ? root.paramsModel.syncronized : false
            Layout.alignment: Qt.AlignRight || Qt.AlignTop
            Layout.preferredWidth: grid.cellWidth
        }
        Indicator {
            labelText: 'TcSync'
            valueState: root.paramsModel ? root.paramsModel.tcSync : false
            Layout.alignment: Qt.AlignLeft || Qt.AlignTop
            Layout.preferredWidth: grid.cellWidth
        }
        Indicator {
            labelText: 'Sync Master'
            valueState: root.paramsModel ? root.paramsModel.syncMaster : false
            Layout.alignment: Qt.AlignRight || Qt.AlignTop
            Layout.preferredWidth: grid.cellWidth
        }
        Item { Layout.preferredWidth: grid.cellWidth }
        Item { Layout.columnSpan: 2; Layout.fillHeight: true }
        TextInput {
            labelText: 'Set Address'
            valueText: root.address

            Layout.columnSpan: 2
            Layout.alignment: Qt.AlignHCenter || Qt.AlignTop
            Layout.preferredWidth: grid.cellWidth * 2

            onTextEdited: {
                root.address = value;
                root.hasChanges = true;
                var props = root.changedProps.slice();
                if (!props.includes('address')){
                    props.push('address');
                    root.changedProps = props;
                }
            }
        }
    }
}
