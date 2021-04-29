import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import DeviceModels 1.0
import UmdModels 1.0

Dialog {
    id: root
    property alias deviceIndex: model.deviceIndex
    property TallyMapModel programModel: model.program
    property TallyMapModel previewModel: model.preview
    property bool isValid: true
    property UmdModel umdModel

    anchors.centerIn: Overlay.overlay
    modal: true
    standardButtons: Dialog.Ok | Dialog.Cancel | Dialog.Apply

    title: 'Add Tally Map'

    TallyCreateMapModel {
        id: model
    }

    onDeviceIndexChanged: { checkValid() }

    Connections {
        target: root.programModel
        function onTallyTypeChanged() { root.checkValid() }
        function onTallyIndexChanged() { root.checkValid() }
    }

    Connections {
        target: root.previewModel
        function onTallyTypeChanged() { root.checkValid() }
        function onTallyIndexChanged() { root.checkValid() }
    }

    onAccepted: {
        checkValid();
        if (isValid){
            applyMap();
        }
        // resetValues();
    }
    onApplied: {
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
        var okBtn = standardButton(Dialog.Ok),
            applyBtn = standardButton(Dialog.Apply);
        okBtn.enabled = isValid;
        applyBtn.enabled = isValid;
    }

    function checkValid(){
        isValid = model.checkValid();
    }

    function applyMap(){
        model.applyMap(umdModel);
    }

    function resetValues(){
        programModel.tallyKey = [-1, -1];
        programModel.tallyType = '';
        previewModel.tallyKey = [-1, -1];
        previewModel.tallyType = '';
        checkValid();
    }

    ColumnLayout {
        TextInput {
            labelText: 'Device Index'
            valueText: root.deviceIndex.toString()
            onSubmit: { root.deviceIndex = parseInt(value) }
        }
        MyGroupBox {
            title: 'Program Tally'
            content: RowLayout {
                TextInput {
                    labelText: 'Screen Index'
                    valueText: root.programModel ? root.programModel.screenIndex.toString() : -1
                    onSubmit: { root.programModel.screenIndex = parseInt(value) }
                }
                TextInput {
                    labelText: 'Tally Index'
                    valueText: root.programModel ? root.programModel.tallyIndex.toString() : -1
                    onSubmit: { root.programModel.tallyIndex = parseInt(value) }
                }
                Column {
                    ButtonGroup {
                        id: programTallyTypeGroup
                        property string value: root.programModel ? root.programModel.tallyType : ''
                        onValueChanged: {
                            var btns = buttons, btn;
                            for (var i=0;i<btns.length;i++){
                                btn = btns[i];
                                if (value == ''){
                                    btn.checked = false;
                                } else if (btn.text == value){
                                    btn.checked = true;
                                }
                            }
                        }
                    }
                    Repeater {
                        model: ['rh_tally', 'txt_tally', 'lh_tally']
                        delegate: RadioDelegate {
                            text: modelData
                            ButtonGroup.group: programTallyTypeGroup
                            onToggled: {
                                if (checked){
                                    root.programModel.tallyType = text;
                                }
                            }
                        }
                    }
                }
            }
        }
        MyGroupBox {
            title: 'Preview Tally'
            content: RowLayout {
                TextInput {
                    labelText: 'Screen Index'
                    valueText: root.previewModel ? root.previewModel.screenIndex.toString() : -1
                    onSubmit: { root.previewModel.screenIndex = parseInt(value) }
                }
                TextInput {
                    labelText: 'Tally Index'
                    valueText: root.previewModel ? root.previewModel.tallyIndex.toString() : -1
                    onSubmit: { root.previewModel.tallyIndex = parseInt(value) }
                }
                Column {
                    ButtonGroup {
                        id: previewTallyTypeGroup
                        property string value: root.previewModel ? root.previewModel.tallyType : ''
                        onValueChanged: {
                            var btns = buttons, btn;
                            for (var i=0;i<btns.length;i++){
                                btn = btns[i];
                                if (value == ''){
                                    btn.checked = false;
                                } else if (btn.text == value){
                                    btn.checked = true;
                                }
                            }
                        }
                    }
                    Repeater {
                        model: ['rh_tally', 'txt_tally', 'lh_tally']
                        delegate: RadioDelegate {
                            text: modelData
                            ButtonGroup.group: previewTallyTypeGroup
                            onToggled: {
                                if (checked){
                                    root.previewModel.tallyType = text;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
