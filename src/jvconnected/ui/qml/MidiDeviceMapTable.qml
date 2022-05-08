import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15 as QQC2
import QtQuick.Controls 1.4 as QQC1
import QtQuick.Extras 1.4
import DeviceModels 1.0
import MidiModels 1.0
import Controls 1.0
import Fonts 1.0

QQC2.Control {
    id: root

    property EngineModel engine
    signal submit()
    signal cancel()

    padding: 8

    onSubmit: {
        deviceMapModel.apply();
    }

    onCancel: {
        deviceMapModel.reset();
    }

    DeviceMapsModel {
        id: deviceMapModel
        engine: root.engine
    }

    QQC2.GroupBox {
        title: 'Mapped Devices'

        anchors.fill: parent

        QQC1.TableView {
            id: deviceMapTable
            anchors.fill: parent
            // implicitWidth: 200
            model: deviceMapModel.proxyModel ? deviceMapModel.proxyModel : null

            sortIndicatorVisible: true

            onSortIndicatorColumnChanged: {
                var col = getColumn(sortIndicatorColumn);
                deviceMapModel.setSorting(col.role, sortIndicatorOrder);
            }

            onSortIndicatorOrderChanged: {
                var col = getColumn(sortIndicatorColumn);
                deviceMapModel.setSorting(col.role, sortIndicatorOrder);
            }

            Component.onCompleted: {
                sortIndicatorColumn = 0;
                sortIndicatorOrder = Qt.DescendingOrder;
                sortIndicatorOrder = Qt.AscendingOrder;
            }

            Component {
                id: indicatorDelegate
                StatusIndicator {
                    color: '#00ff00'
                    active: styleData.value
                }
            }

            Component {
                id: channelDelegate
                Row {
                    id: delegateRoot
                    property string deviceId: model ? model.deviceId : ''
                    property int editValue: styleData.value
                    property string textValue: editValue < 0 ? '' : editValue.toString()
                    property bool edited: model ? model.edited : false

                    QQC2.Label {
                        id: lbl
                        padding: 0
                        text: textValue
                    }
                    Item {
                        width: parent.width - lbl.width - upBtn.width - dnBtn.width - undoBtn.width - unMapBtn.width
                        height: 1
                    }
                    ArrowButton {
                        id: upBtn
                        height: parent.height
                        width: styleData.selected ? height : 0
                        enabled: styleData.selected
                        round: false
                        direction: Qt.UpArrow
                        onClicked: {
                            deviceMapModel.incrementChannel(deviceId);
                        }
                    }
                    ArrowButton {
                        id: dnBtn
                        height: parent.height
                        width: styleData.selected ? height : 0
                        enabled: styleData.selected
                        round: false
                        direction: Qt.DownArrow
                        onClicked: {
                            deviceMapModel.decrementChannel(deviceId);
                        }
                    }
                    IconButton {
                        id: undoBtn
                        height: parent.height
                        width: styleData.selected ? height : 0
                        enabled: styleData.selected && delegateRoot.edited
                        round: false
                        iconName: 'faUndo'
                        pointSize: 9
                        hoverEnabled: true
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.text: 'Undo'
                        onClicked: {
                            deviceMapModel.resetChannel(deviceId);
                        }
                    }
                    IconButton {
                        id: unMapBtn
                        height: parent.height
                        width: styleData.selected ? height : 0
                        enabled: styleData.value >= 0
                        round: false
                        iconName: 'faTimesCircle'
                        pointSize: 9
                        hoverEnabled: true
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.text: 'Unassign Channel'
                        onClicked: {
                            deviceMapModel.unassignChannel(deviceId);
                        }
                    }
                }
            }

            QQC1.TableViewColumn {
                role: 'deviceIndex'
                title: 'Device Index'
                width: 100
            }

            QQC1.TableViewColumn {
                role: 'deviceName'
                title: 'Device Name'
                width: 100
            }

            QQC1.TableViewColumn {
                role: 'channel'
                title: 'Midi Channel'
                width: 100
                delegate: channelDelegate
            }

            QQC1.TableViewColumn {
                role: 'isOnline'
                title: 'Online'
                width: 100
                delegate: indicatorDelegate
            }
            QQC1.TableViewColumn {
                role: 'edited'
                title: 'Edited'
                width: 100
                delegate: indicatorDelegate
            }
        }
    }
}
