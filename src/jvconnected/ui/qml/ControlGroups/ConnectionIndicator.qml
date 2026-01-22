import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Controls
import DeviceModels

Indicator {
    id: root
    labelText: 'Connection Status'
    states: [
        State {
            name: 'unknown'
            PropertyChanges { target: root; valueState: false; activeColor: '#808080' }
        },
        State {
            name: 'scheduling'
            PropertyChanges { target: root; valueState: UiState.blinker; activeColor: '#00ff00'}
        },
        State {
            name: 'sleeping'
            PropertyChanges { target: root; valueState: UiState.blinker; activeColor: '#00ff00'}
        },
        State {
            name: 'attempting'
            PropertyChanges { target: root; valueState: UiState.blinker; activeColor: '#00ff00'}
        },
        State {
            name: 'connected'
            PropertyChanges { target: root; valueState: true; activeColor: '#00ff00' }
        },
        State {
            name: 'failed'
            PropertyChanges { target: root; valueState: true; activeColor: '#ff0000' }
        },
        State {
            name: 'disconnect'
            PropertyChanges { target: root; valueState: false; activeColor: '#00ff00' }
        }
    ]
}
