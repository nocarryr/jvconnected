import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

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
                }
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
                        text: '\uD83D\uDDD9'
                        onClicked: {
                            root.device.removeDeviceIndex(root.device.deviceIndex);
                        }
                    }
                }
            }
            Indicator {
                labelText: 'Online'
                valueState: root.confDevice ? root.confDevice.deviceOnline : false
            }
            Indicator {
                labelText: 'Active'
                valueState: root.confDevice ? root.confDevice.deviceActive : false
            }
            Indicator {
                labelText: 'Stored'
                valueState: root.confDevice ? root.confDevice.storedInConfig : false
            }
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
                title: 'Iris'
                Layout.fillWidth: true

                content: ColumnLayout {

                    RowLayout {

                        Label {
                            text: 'Mode'
                        }

                        Item { }

                        ComboBox {
                            property string currentMode: root.model.iris.mode
                            model: ['Auto', 'Manual']

                            function updateCurrentMode(){
                                if (typeof(currentMode) != 'undefined'){
                                    currentIndex = indexOfValue(currentMode);
                                }
                            }

                            onCurrentModeChanged: { updateCurrentMode() }

                            Component.onCompleted: { updateCurrentMode() }

                            onActivated: {
                                var modeBool = true ? currentText == 'Auto' : false
                                root.model.iris.setAutoIris(modeBool);
                                updateCurrentMode();
                            }
                        }
                    }

                    RowLayout {

                        ValueLabel {
                            labelText: 'F-Stop'
                            valueText: model.iris.fstop
                            orientation: Qt.Vertical
                        }

                        Item { Layout.fillWidth: true }

                        LeftRightButtons {
                            enabled: model.iris.mode == 'Manual'
                            onRightClicked: model.iris.increase()
                            onLeftClicked: model.iris.decrease()
                        }

                        Slider {
                            enabled: model.iris.mode == 'Manual'
                            orientation: Qt.Horizontal
                            from: 0
                            to: 255
                            stepSize: 1
                            snapMode: Slider.SnapAlways
                            property real irisValue: model.iris.pos
                            property bool captured: false
                            onIrisValueChanged: {
                                if (!captured){
                                    value = irisValue;
                                }
                            }
                            onPressedChanged: {
                                captured = pressed;
                            }
                            onValueChanged: {
                                if (captured && pressed){
                                    model.iris.setPos(value);
                                }
                            }
                        }
                    }
                }
            }

            CollapseGroupBox {
                title: 'Gain'
                Layout.fillWidth: true

                content: ColumnLayout {
                    // anchors.fill: parent

                    ValueLabel {
                        labelText: 'Mode'
                        valueText: model.gainMode.value
                        Layout.fillWidth: true
                    }

                    RowLayout {

                        ValueLabel {
                            labelText: 'Value'
                            valueText: model.gainValue.value
                        }

                        Item { Layout.fillWidth: true }

                        UpDownButtons {
                            onUpClicked: model.gainValue.increase()
                            onDownClicked: model.gainValue.decrease()
                        }
                    }
                }
            }

            CollapseGroupBox {
                title: 'Master Black'
                Layout.fillWidth: true

                content: RowLayout {
                    // anchors.fill: parent

                    ValueLabel {
                        labelText: 'Value'
                        valueText: model.masterBlack.value
                    }

                    Item { Layout.fillWidth: true }

                    UpDownButtons {
                        onUpClicked: model.masterBlack.increase()
                        onDownClicked: model.masterBlack.decrease()
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
                            RowLayout {
                                Label {
                                    text: 'Mode'
                                }
                                Item { }
                                ComboBox {
                                    property string currentMode: root.model.paint.mode.value

                                    model: [
                                        'Faw', 'Preset', 'A', 'B', 'Adjust',
                                        'WhPaintRP', 'WhPaintRM', 'WhPaintBP', 'WhPaintBM',
                                        'Awb', '3200K', '5600K', 'Manual',
                                    ]

                                    onCurrentModeChanged: { updateCurrentMode() }

                                    function updateCurrentMode(){
                                        if (typeof(currentMode) != 'undefined'){
                                            currentIndex = indexOfValue(currentMode);
                                        }
                                    }

                                    Component.onCompleted: { updateCurrentMode() }

                                    onActivated: {
                                        root.model.paint.mode.setMode(currentText);
                                        updateCurrentMode();
                                    }
                                }
                            }
                            ValueLabel {
                                labelText: 'Color Temp'
                                valueText: model.paint.colorTemp.value
                            }
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
                RowLayout {
                    anchors.fill: parent
                    Label {
                        text: 'Tally Status'
                    }
                    Item { Layout.fillWidth: true }
                    ToolButton {
                        id: pgmTallyBtn
                        text: 'PGM'
                        // enabled: false
                        checkable: true
                        checked: model.tally.program
                        onToggled: {
                            model.tally.setProgram(checked);
                        }
                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 40
                            // visible: !control.flat || control.down || control.checked || control.highlighted
                            color: pgmTallyBtn.checked ? '#ff0000' : '#800000'
                            // color: Color.blend(control.checked || control.highlighted ? control.palette.dark : control.palette.button,
                            //                                                             control.palette.mid, control.down ? 0.5 : 0.0)
                            border.color: pgmTallyBtn.palette.highlight
                            // border.width: control.visualFocus ? 2 : 0
                        }
                    }
                    ToolButton {
                        id: pvwTallyBtn
                        text: 'PVW'
                        // enabled: false
                        checkable: true
                        checked: model.tally.preview
                        onToggled: {
                            model.tally.setPreview(checked);
                        }
                        background: Rectangle {
                            implicitWidth: 80
                            implicitHeight: 40
                            color: pvwTallyBtn.checked ? '#00ff00' : '#008000'
                            border.color: pvwTallyBtn.palette.highlight
                        }
                    }
                }
            }
        }
    }
}
