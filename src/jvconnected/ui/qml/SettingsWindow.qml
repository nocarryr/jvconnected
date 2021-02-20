import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

Dialog {
    id: root
    title: 'Settings'
    standardButtons: Dialog.Ok | Dialog.Cancel | Dialog.Apply | Dialog.Reset

    property EngineModel engine

    MyTabBar {
        id: bar
        width: parent.width

        MyTabButton { text: 'Devices'; width: bar.maxItemWidth }
        MyTabButton { text: 'Midi'; width: bar.maxItemWidth }
        MyTabButton { text: 'Tally'; width: bar.maxItemWidth }
    }

    StackLayout {
        id: stack
        currentIndex: bar.currentIndex
        anchors.top: bar.bottom
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 8

        CameraSettingsList {
            id: camSettings
            engine: root.engine
            // anchors.fill: parent
            Connections {
                target: root
                function onAccepted() { camSettings.submit() }
                function onApplied() { camSettings.submit() }
                function onRejected() { camSettings.cancel() }
                function onReset() { camSettings.cancel() }
            }
        }

        MidiSettings {
            id: midiSettings
            engine: root.engine
        }
        TallySettings {
            id: tallySettings
            engine: root.engine
            Connections {
                target: root
                function onAccepted() { tallySettings.submit() }
                function onApplied() { tallySettings.submit() }
                function onRejected() { tallySettings.cancel() }
                function onReset() { tallySettings.cancel() }
            }
        }
    }


    // onAccepted: {
    //
    // }
}
