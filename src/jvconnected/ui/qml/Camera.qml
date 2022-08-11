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
    // NOTE: width should be 390

    onDeviceIndexChanged: {
        deviceIndexUpdate();
    }

    function showOptionsDialog(){
        optionsDialog.reset();
        optionsDialog.open();
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
        implicitWidth: 376

        content: ColumnLayout {
            // NOTE: width should be 376

            ColumnLayout {
                // NOTE: width should be 360
                RowLayout {
                    // NOTE: width should be 342
                    ValueLabel {
                        labelText: 'Index'
                        valueText: root.device.deviceIndex
                        orientation: Qt.Horizontal
                    }
                    Item { Layout.fillWidth: true }
                    ValueLabel {
                        labelText: 'Name'
                        valueText: root.device.displayName
                        orientation: Qt.Horizontal
                    }
                    Item { Layout.fillWidth: true }
                    IconButton {
                        iconName: 'faCog'
                        onClicked: { root.showOptionsDialog() }
                    }
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
                            title: 'Master Black'
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            content: MasterBlackControls { model: root.model }
                        }
                        MyGroupBox {
                            title: 'Gain'
                            Layout.fillWidth: true
                            Layout.fillHeight: true

                            content: GainControls { model: root.model }
                        }
                    }
                }
            }

            PanelGroup {
                title: 'Lens'
                groupName: 'lens'
                Layout.fillWidth: true

                content: ColumnLayout {
                    MyGroupBox {
                        title: 'Focus'
                        Layout.fillWidth: true
                        content: FocusControls { model: root.model }
                    }
                    MyGroupBox {
                        title: 'Zoom'
                        Layout.fillWidth: true
                        content: ZoomControls { model: root.model }
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

    Component {
        id: optionsDialogComponent
        CameraOptionsDialog {
            deviceModel: root.model
            width: 600
            height: 400
            modal: true
            focus: true
            parent: Overlay.overlay
            x: Math.round((parent.width - width) / 2)
            y: Math.round((parent.height - height) / 2)
        }
    }

    Loader {
        id: optionsDialog

        function open(){
            var status = optionsDialog.status;
            if (status == Loader.Null){
                optionsDialog.sourceComponent = optionsDialogComponent;
            } else if (status == Loader.Ready){
                optionsDialog.item.open();
            }
        }

        function reset(){
            if (optionsDialog.status == Loader.Ready){
                optionsDialog.item.reset();
            }
        }

        onLoaded: {
            optionsDialog.item.reset();
            optionsDialog.item.open();
        }
    }
}
