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
    property UmdModel umdModel

    standardButtons: Dialog.Ok | Dialog.Cancel

    title: 'UnMap Tally'

    function updateModel(){
        listModel.clear();
        var mapped = model.getMappedDeviceIndices(umdModel);
        var ix;
        for (var i=0;i<mapped.length;i++){
            ix = mapped[i];
            console.log(i, ix);
            listModel.append({'deviceIndex':ix, 'isChecked':true, 'displayText':ix.toString()});
        }
    }

    onAccepted: {
        var indices = [], item;
        for (var i=0;i<listModel.count;i++){
            item = listModel.get(i);
            if (item.isChecked){
                indices.push(item.deviceIndex);
            }
        }
        model.unmapByIndices(umdModel, indices);
    }

    TallyUnmapModel {
        id: model
    }

    ListModel {
        id: listModel
        dynamicRoles: true
    }

    ColumnLayout {
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
                Layout.fillHeight: true
                orientation: Qt.Vertical
                labelText: 'Source Index'
                valueText: root.tallyIndex.toString()
            }
            ValueLabel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                orientation: Qt.Vertical
                labelText: 'Tally Type'
                valueText: root.tallyType
            }
        }
        GridLayout {
            columns: 2
            Label {
                text: 'Device Indices'
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.alignment: Layout.AlignVCenter | Layout.AlignLeft
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            ListView {
                implicitWidth: 300
                implicitHeight: 300
                id: listView
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: listModel
                delegate: CheckDelegate {
                    text: displayText
                    checked: isChecked
                    onToggled: {
                        listModel.setProperty(index, 'isChecked', checked);
                    }
                }
            }
        }
    }
}
