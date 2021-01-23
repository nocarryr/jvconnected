import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0
import ControlGroups 1.0
import Fonts 1.0

Control {
    id: root
    property DeviceModel device
    property DeviceConfigModel confDevice: device ? device.confDevice : null
    property string labelText: device ? device.displayName : 'Unknown Camera'
    property bool connected: device ? device.connected : false
    property alias deviceIndex: model.deviceIndex
    property CameraModel model: model
    signal deviceIndexUpdate()

    onDeviceIndexChanged: {
        deviceIndexUpdate();
    }

    // Layout.leftMargin: 4
    // Layout.rightMargin: 4
    Layout.alignment: Qt.AlignLeft | Qt.AlignTop
    // Layout.column: deviceIndex
    horizontalPadding: 4

    CameraModel {
        id: model
        device: root.device
    }

    contentItem: MyGroupBox {
        // anchors.fill: parent
        title: root.labelText
        headerBackgroundColor: '#8080ca'
        horizontalPadding: 8

        content: ColumnLayout {

            ColumnLayout {
                ValueLabel {
                    labelText: 'Index'
                    valueText: root.device.deviceIndex
                    orientation: Qt.Horizontal
                    Layout.fillWidth: true
                }
                BatteryControls { model: root.model }
                RowLayout {
                    LeftRightButtons {
                        onLeftClicked: {
                            var ix = root.device.deviceIndex - 1;
                            if (ix < 0){
                                return;
                            }
                            root.device.setDeviceIndex(ix);
                        }
                        onRightClicked: {
                            var ix = root.device.deviceIndex + 1;
                            root.device.setDeviceIndex(ix);
                        }
                    }
                    RoundButton {
                        id: removeIndexBtn
                        property IconFont iconFont: IconFont {
                            iconName: 'faTimes'
                        }
                        text: iconFont.text
                        font: iconFont.iconFont
                        onClicked: {
                            root.device.removeDeviceIndex(root.device.deviceIndex);
                        }
                    }
                }
            }
            ConnectionControls { model: root.model }
            ValueLabel {
                labelText: 'Status'
                valueText: root.connected ? 'Connected' : 'Not Connected'
                Layout.fillWidth: true
            }
            ValueLabel {
                labelText: 'TC'
                valueText: model.cameraParams.timecode
                Layout.fillWidth: true
            }

            CollapseGroupBox {
                title: 'Video Preview'
                Layout.fillWidth: true
                onIsCollapsedChanged: {
                    previewWindow.setVideoEnabled(!isCollapsed);
                }
                content: ColumnLayout {
                    CameraPreview {
                        id: previewWindow
                        Layout.fillWidth: true
                        Layout.preferredHeight: width * .5625
                        fillColor: '#000000ff'
                        device: root.device
                        onHeightChanged: { triggerUpdate() }
                        onWidthChanged: { triggerUpdate() }
                        onXChanged: { triggerUpdate() }
                        onYChanged: { triggerUpdate() }
                        onVideoEnabledChanged: {
                            previewEnableBtn.checked = videoEnabled;
                        }
                    }
                    Switch {
                        id: previewEnableBtn
                        checked: false
                        onToggled: {
                            previewWindow.setVideoEnabled(checked);
                        }
                    }
                    MenuButtons {
                        id: menuButtons
                        menuActive: model.cameraParams.menuStatus
                        onClicked: {
                            root.model.cameraParams.sendMenuButton(buttonType);
                        }
                    }
                }
            }

            CollapseGroupBox {
                title: 'Exposure'
                Layout.fillWidth: true

                content: ColumnLayout {
                    MyGroupBox {
                        title: 'Iris'
                        content: IrisControls { model: root.model }
                    }
                    MyGroupBox {
                        title: 'Gain'
                        Layout.fillWidth: true

                        content: GainControls { model: root.model }
                    }
                    MyGroupBox {
                        title: 'Master Black'
                        Layout.fillWidth: true

                        content: MasterBlackControls { model: root.model }
                    }
                }
            }

            CollapseGroupBox {
                title: 'Paint'
                Layout.fillWidth: true

                content: ColumnLayout {
                    MyGroupBox {
                        title: 'Detail'

                        content: RowLayout {
                            ValueLabel {
                                labelText: 'Value'
                                valueText: model.detail.value
                            }
                            LeftRightButtons {
                                onRightClicked: model.detail.increase()
                                onLeftClicked: model.detail.decrease()
                            }
                        }
                    }
                    MyGroupBox {
                        title: 'White Balance'
                        content: ColumnLayout {
                            WhiteBalanceControls { model: root.model }
                            PaintControl {
                                model: model
                                // colorType: PaintControl.ColorType.Red
                            }
                        }
                    }
                }
            }
            ToolBar {
                position: ToolBar.Footer
                Layout.fillWidth: true
                TallyControls { model: root.model }
            }
        }
    }
}
