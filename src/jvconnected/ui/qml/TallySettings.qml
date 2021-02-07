import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15 as QQC2
import QtQuick.Controls 1.4 as QQC1
import Qt.labs.settings 1.0
import DeviceModels 1.0
import UmdModels 1.0
import Controls 1.0

QQC2.Control {
    id: root
    property alias hostaddr: umdModel.hostaddr
    property alias hostport: umdModel.hostport
    property bool hasChanges: false

    property EngineModel engine

    UmdModel {
        id: umdModel
        engine: root.engine
    }

    TallyListModel {
        id: listModel
        engine: root.engine
        onLayoutChanged: { tallyTable.resizeColumnsToContents() }
        onDataChanged: { tallyTable.resizeColumnsToContents() }
    }

    signal submit()
    signal cancel()

    onSubmit: { setInterfaceValues() }

    onCancel: { updateFromInterface() }

    function updateFromInterface(){
        checkValues();
        umdModel.getValuesFromInterface();
        checkValues();
    }

    function setInterfaceValues(){
        if (hasChanges){
            umdModel.sendValuesToInterface();
            checkValues();
        }
        updateFromInterface();
    }

    function checkValues(){
        hasChanges = umdModel.editedProperties.length > 0
    }

    Connections {
        target: umdModel
        function onEditedPropertiesChanged() {
            checkValues();
        }
    }

    contentItem: RowLayout {
        ColumnLayout {
            Layout.preferredWidth: 100
            Layout.fillHeight: true
            Indicator {
                orientation: Qt.Vertical
                labelText: 'Running'
                valueState: umdModel.running
            }
            TextInput {
                labelText: 'Host Address'
                valueText: umdModel.hostaddr
                Layout.fillWidth: true
                onSubmit: {
                    umdModel.hostaddr = value;
                    root.checkValues();
                }
            }
            TextInput {
                labelText: 'Host Port'
                valueText: root.hostport.toString()
                Layout.fillWidth: true
                onSubmit: {
                    umdModel.hostport = parseInt(value);
                    root.checkValues();
                }
            }
        }
        QQC1.TableView {
            id: tallyTable
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: listModel
            QQC1.TableViewColumn {
                role: 'tallyIndex'
                title: 'Index'
            }
            QQC1.TableViewColumn {
                role: 'rhTally'
                title: 'rhTally'
                delegate: Item {
                    implicitWidth: 40
                    Rectangle {
                        width: height
                        height: parent.height
                        anchors.centerIn: parent
                        color: styleData.value
                    }
                }
            }
            QQC1.TableViewColumn {
                role: 'txtTally'
                title: 'txtTally'
                delegate: Item {
                    implicitWidth: 40
                    Rectangle {
                        width: height
                        height: parent.height
                        anchors.centerIn: parent
                        color: styleData.value
                    }
                }
            }
            QQC1.TableViewColumn {
                role: 'lhTally'
                title: 'lhTally'
                delegate: Item {
                    implicitWidth: 40
                    Rectangle {
                        width: height
                        height: parent.height
                        anchors.centerIn: parent
                        color: styleData.value
                    }
                }
            }
            QQC1.TableViewColumn {
                role: 'text'
                title: 'text'
            }
        }
    }
}
