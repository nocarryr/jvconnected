import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import DeviceModels 1.0
import UmdModels 1.0

Dialog {
    id: root
    property alias tallyKey: model.tallyKey
    property alias screenIndex: model.screenIndex
    property alias tallyIndex: model.tallyIndex
    property alias tallyType: model.tallyType       // 'lh_tally' | 'txt_tally' | 'rh_tally'
    property alias deviceIndex: model.deviceIndex
    property alias destTallyType: model.destTallyType   // 'Program' | 'Preview'
    property bool isValid: true
    property UmdModel umdModel

    standardButtons: Dialog.Ok | Dialog.Cancel

    title: 'Map Tally'

    TallyMapModel {
        id: model
    }

    onAccepted: {
        checkValid();
        if (isValid){
            applyMap();
        }
    }
    onRejected: {
        resetValues();
    }
    onIsValidChanged: {
        console.log('isValid: ', isValid);
        var applyBtn = standardButton(Dialog.Ok);
        applyBtn.enabled = isValid;
    }
    onTallyKeyChanged: { checkValid() }
    onTallyTypeChanged: { checkValid() }
    onDeviceIndexChanged: { checkValid() }
    onDestTallyTypeChanged: { checkValid() }

    function applyMap(){
        console.log(JSON.stringify({'tallyKey':tallyKey, 'tallyType':tallyType, 'deviceIndex':deviceIndex, 'destTallyType':destTallyType}));
        model.applyMap(umdModel);
    }

    function resetValues(){
        tallyKey = [-1, -1];
        tallyType = '';
        destTallyType = '';
    }

    function checkValid(){
        isValid = model.checkValid();
    }

    ColumnLayout {
        anchors.fill: parent
        GridLayout {
            columns: 2
            Label {
                text: 'Source'
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.alignment: Layout.AlignVCenter | Layout.AlignLeft
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            ValueLabel {
                Layout.fillWidth: true
                orientation: Qt.Vertical
                labelText: 'Screen Index'
                valueText: root.screenIndex.toString()
            }
            ValueLabel {
                Layout.fillWidth: true
                orientation: Qt.Vertical
                labelText: 'Tally Index'
                valueText: root.tallyIndex.toString()
            }
            ValueLabel {
                Layout.fillWidth: true
                orientation: Qt.Vertical
                labelText: 'Tally Type'
                valueText: root.tallyType
            }
        }
        GridLayout {
            columns: 2
            Label {
                text: 'Destination'
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.alignment: Layout.AlignVCenter | Layout.AlignLeft
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            TextInput {
                labelText: 'Device Index'
                valueText: root.deviceIndex.toString()
                Layout.fillWidth: true
                orientation: Qt.Vertical
                onSubmit: { root.deviceIndex = parseInt(value) }
            }
            Column {
                Layout.fillWidth: true
                RadioButton {
                    text: 'Program'
                    onToggled: {
                        if (checked){
                            root.destTallyType = text;
                        }
                    }
                }
                RadioButton {
                    text: 'Preview'
                    onToggled: {
                        if (checked){
                            root.destTallyType = text;
                        }
                    }
                }
            }
        }
    }
}
