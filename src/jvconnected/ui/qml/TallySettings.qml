import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15 as QQC2
import QtQuick.Controls 1.4 as QQC1
import QtQuick.Extras 1.4
import Qt.labs.settings 1.0
import DeviceModels 1.0
import UmdModels 1.0
import Controls 1.0
import Fonts 1.0

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
        Component.onCompleted: { tallyTable.resizeColumnsToContents() }
    }

    TallyMapListModel {
        id: mapListModel
        engine: root.engine
        onLayoutChanged: { tallyMapTable.resizeColumnsToContents() }
        onDataChanged: { tallyMapTable.resizeColumnsToContents() }
        Component.onCompleted: { tallyMapTable.resizeColumnsToContents() }
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

    contentItem: GridLayout {
        columns: 2
        RowLayout {
            Layout.columnSpan: 2
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
                orientation: Qt.Vertical
                Layout.fillWidth: true
                onSubmit: {
                    umdModel.hostaddr = value;
                    root.checkValues();
                }
            }
            TextInput {
                labelText: 'Host Port'
                valueText: root.hostport.toString()
                orientation: Qt.Vertical
                Layout.fillWidth: true
                onSubmit: {
                    umdModel.hostport = parseInt(value);
                    root.checkValues();
                }
            }
        }
        QQC1.TableView {
            id: tallyMapTable
            Layout.row: 1
            Layout.column: 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitWidth: 200
            model: mapListModel

            contentFooter: QQC2.ToolBar {
                position: QQC2.ToolBar.Footer
                RowLayout {
                    anchors.fill: parent
                    QQC2.ToolButton {
                        property IconFont iconFont: IconFont {
                            iconName: 'faMinus'
                        }
                        text: iconFont.text
                        font: iconFont.iconFont
                        enabled: tallyMapTable.currentRow != -1
                        onClicked: {
                            var rowIx = tallyMapTable.currentRow;
                            if (rowIx != -1){
                                mapListModel.unMapByRow(rowIx);
                            }
                        }
                    }
                    QQC2.ToolButton {
                        property IconFont iconFont: IconFont {
                            iconName: 'faPlus'
                        }
                        text: iconFont.text
                        font: iconFont.iconFont
                        onClicked: {
                            tallyCreateMapDialog.resetValues();
                            tallyCreateMapDialog.open();
                        }
                    }
                }
            }

            QQC1.TableViewColumn {
                role: 'device_index'
                title: 'Device Index'
                width: 100
            }
            QQC1.TableViewColumn {
                role: 'program.tally_index'
                title: 'PGM Index'
                width: 100
            }
            QQC1.TableViewColumn {
                role: 'program.tally_type'
                title: 'PGM Type'
                width: 100
            }
            QQC1.TableViewColumn {
                role: 'preview.tally_index'
                title: 'PVW Index'
                width: 100
            }
            QQC1.TableViewColumn {
                role: 'preview.tally_type'
                title: 'PVW Type'
                width: 100
            }
        }
        QQC1.TableView {
            id: tallyTable
            Layout.row: 1
            Layout.column: 1
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: listModel

            Component {
                id: tallyTableDelegate
                StatusIndicator {
                    color: styleData.value == 'OFF' ? 'grey' : styleData.value
                    active: styleData.value != 'OFF'
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.RightButton
                        onClicked: {
                            // console.log(styleData.row, styleData.column);
                            var tallyIndex = listModel.getIndexForRow(styleData.row),
                                tallyType = listModel.getTallyTypeForColumn(styleData.column);
                            // console.log(tallyIndex, tallyType);
                            tallyTableCtxMenu.tallyIndex = tallyIndex;
                            tallyTableCtxMenu.tallyType = tallyType;
                            tallyTableCtxMenu.popup();
                        }
                    }
                }
            }

            QQC1.TableViewColumn {
                role: 'tallyIndex'
                title: 'Index'
            }
            QQC1.TableViewColumn {
                role: 'rhTally'
                title: 'rhTally'
                delegate: tallyTableDelegate
            }
            QQC1.TableViewColumn {
                role: 'txtTally'
                title: 'txtTally'
                delegate: tallyTableDelegate
            }
            QQC1.TableViewColumn {
                role: 'lhTally'
                title: 'lhTally'
                delegate: tallyTableDelegate
            }
            QQC1.TableViewColumn {
                role: 'text'
                title: 'text'
            }
            QQC2.Menu {
                id: tallyTableCtxMenu
                property int tallyIndex: -1
                property string tallyType: ''
                QQC2.MenuItem {
                    text: 'Map..'
                    onTriggered: {
                        tallyMapDlg.tallyType = tallyTableCtxMenu.tallyType;
                        tallyMapDlg.tallyIndex = tallyTableCtxMenu.tallyIndex;
                        tallyMapDlg.open();
                    }
                }
                QQC2.MenuItem {
                    text: 'UnMap'
                    onTriggered: {
                        tallyUnmapDialog.tallyType = tallyTableCtxMenu.tallyType;
                        tallyUnmapDialog.tallyIndex = tallyTableCtxMenu.tallyIndex;
                        tallyUnmapDialog.updateModel();
                        tallyUnmapDialog.open();
                    }
                }
            }
        }
    }
    TallyMapDialog {
        id: tallyMapDlg
        umdModel: umdModel
    }
    TallyUnmapDialog {
        id: tallyUnmapDialog
        umdModel: umdModel
    }
    TallyCreateMapDialog {
        id: tallyCreateMapDialog
        umdModel: umdModel
    }
}
