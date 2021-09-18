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
    padding: 8

    CameraModel {
        id: model
        device: root.device
    }

    contentItem: MyGroupBox {
        // anchors.fill: parent
        title: root.labelText
        headerFont.pointSize: 16
        headerBackgroundColor: '#215c98'
        headerTextColor: '#ffffff'
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
            }
            RowLayout {
                ValueLabel {
                    labelText: 'Timecode:'
                    valueText: model.cameraParams.timecode
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
                Item { Layout.fillWidth: true }
                ConnectionControls { model: root.model }
            }

            PanelGroup {
                groupName: 'cameraPreview'
                title: 'Video Preview'
                Layout.fillWidth: true
                onIsCollapsedChanged: {
                    if (isCollapsed){
                        previewWindow.setVideoMode('OFF');
                    } else {
                        previewWindow.setVideoMode(previewWindow.lastVideoMode);
                    }
                }
                content: ColumnLayout {
                    CameraPreview {
                        id: previewWindow
                        property string lastVideoMode: 'VIDEO'
                        Layout.fillWidth: true
                        Layout.preferredHeight: width * .5625
                        device: root.device
                        onHeightChanged: { triggerUpdate() }
                        onWidthChanged: { triggerUpdate() }
                        onXChanged: { triggerUpdate() }
                        onYChanged: { triggerUpdate() }
                        onVideoModeChanged: {
                            var curMode = videoMode;
                            if (typeof(curMode) != 'undefined') {
                                if (curMode != 'OFF') {
                                    lastVideoMode = curMode;
                                }
                                previewModeCombo.updateCurrentMode();
                            }
                        }
                        onLastVideoModeChanged: {
                            var deviceId = root.model.deviceId,
                                mode = lastVideoMode;
                            UiState.panelGroups.setPreviewWindowMode(deviceId, mode);
                        }
                        onDeviceChanged: {
                            var savedMode = getSavedPreviewMode();
                            if (savedMode !== undefined){
                                lastVideoMode = savedMode;
                            }
                        }
                        function getSavedPreviewMode() {
                            if (!root.device) {
                                return undefined;
                            }
                            var deviceId = root.model.deviceId;
                            if (!deviceId.length){
                                return undefined;
                            }
                            return UiState.panelGroups.getPreviewWindowMode(deviceId);
                        }
                        Component.onCompleted: {
                            var savedMode = getSavedPreviewMode();
                            if (savedMode !== undefined){
                                lastVideoMode = savedMode;
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Item {
                            Layout.fillWidth: true
                        }
                        Label {
                            text: 'Mode'
                            horizontalAlignment: Text.AlignRight
                            verticalAlignment: Text.AlignVCenter
                            Layout.alignment: Layout.AlignVCenter | Layout.AlignRight
                        }
                        ComboBox {
                            id: previewModeCombo
                            model: ['Off', 'Video', 'Waveform']

                            function updateCurrentMode(){
                                var curMode = previewWindow.videoMode;
                                if (typeof(curMode) != 'undefined'){
                                    currentIndex = find(curMode, Qt.MatchFixedString);
                                }
                            }

                            Component.onCompleted: { updateCurrentMode() }

                            onActivated: {
                                previewWindow.setVideoMode(currentValue);
                                updateCurrentMode();
                            }
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
                Component.onCompleted: {
                    if (!isCollapsed){
                        previewWindow.setVideoMode(previewWindow.lastVideoMode);
                    }
                }
            }

            PanelGroup {
                title: 'Exposure'
                groupName: 'exposure'
                Layout.fillWidth: true

                content: ColumnLayout {
                    MyGroupBox {
                        title: 'Iris'
                        Layout.fillWidth: true
                        content: IrisControls { model: root.model }
                    }
                    RowLayout {
                        MyGroupBox {
                            title: 'Gain'
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            content: GainControls { model: root.model }
                        }
                        MyGroupBox {
                            title: 'Master Black'
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            content: MasterBlackControls { model: root.model }
                        }
                    }
                }
            }

            PanelGroup {
                title: 'Paint'
                groupName: 'paint'
                Layout.fillWidth: true

                content: ColumnLayout {
                    RowLayout {
                        MyGroupBox {
                            title: 'White Balance'
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            content: ColumnLayout {
                                WhiteBalanceControls { model: root.model }
                            }
                        }
                        MyGroupBox {
                            title: 'Detail'
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            content: DetailControls { model: root.model }
                        }
                    }
                    MyGroupBox {
                        title: 'Wb Paint Adjust'
                        Layout.fillWidth: true
                        content: PaintControl {
                            model: model
                            Layout.fillWidth: true
                        }
                    }
                }
            }
            ToolBar {
                position: ToolBar.Footer
                Layout.fillWidth: true
                TallyControls { Layout.fillWidth: true; model: root.model }
            }
        }
    }
    background: Rectangle {
        color: root.model.tally.program ? '#ff0000' : root.model.tally.preview ? '#00e000' : 'transparent'
        border.color: root.palette.dark
        border.width: 2
        radius: 6
        Rectangle {
            color: root.palette.window
            x: root.leftPadding
            y: parent.y + root.topPadding
            width: root.availableWidth
            height: root.availableHeight
        }
    }
}
