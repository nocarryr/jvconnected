import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import DeviceModels 1.0
import UmdModels 1.0

Dialog {
    id: root
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
        // resetValues();
    }
    onRejected: {
        resetValues();
    }
    onIsValidChanged: {
        console.log('isValid: ', isValid);
        var applyBtn = standardButton(Dialog.Ok);
        applyBtn.enabled = isValid;
    }
    onTallyIndexChanged: { checkValid() }
    onTallyTypeChanged: { checkValid() }
    onDeviceIndexChanged: { checkValid() }
    onDestTallyTypeChanged: { checkValid() }

    function applyMap(){
        console.log(JSON.stringify({'tallyIndex':tallyIndex, 'tallyType':tallyType, 'deviceIndex':deviceIndex, 'destTallyType':destTallyType}));
        model.applyMap(umdModel);
    }

    function resetValues(){
        tallyIndex = -1;
        tallyType = '';
        // deviceIndex = 0;
        destTallyType = '';
    }

    function checkValid(){
        isValid = model.checkValid();
        // if (tallyIndex < 0 || deviceIndex < 0){
        //     isValid = false;
        // }
        // else if (!tallyType.length || !destTallyType.length){
        //     isValid = false;
        // } else {
        //     isValid = true;
        // }
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
                labelText: 'Source Index'
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
