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

    property EngineModel engine

    TallyListModel {
        id: listModel
        engine: root.engine
    }

    contentItem: QQC1.TableView {
        model: listModel
        QQC1.TableViewColumn {
            role: 'tallyIndex'
            title: 'Index'
        }
        QQC1.TableViewColumn {
            role: 'rhTally'
            title: 'rhTally'
            delegate: Item {
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
