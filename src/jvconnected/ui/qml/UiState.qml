pragma Singleton

import QtQuick 2.15
import Qt.labs.settings 1.0

QtObject {
    id: root
    property string foo: 'bar'

    property QtObject panelGroups: QtObject {
        id: panelGroupsObj
        property var groupStates: ({})
        property var previewWindowModes: ({})

        signal stateUpdated(string name, string newState)

        property Settings settings: Settings {
            category: "PanelGroups"
            property alias groupStates: panelGroupsObj.groupStates
            property alias previewWindowModes: panelGroupsObj.previewWindowModes
        }

        function getGroupState(name){
            if (typeof(name) != 'string'){
                return undefined;
            }
            var groupState = groupStates[name];
            if (groupState === undefined){
                groupState = 'collapsed';
                groupStates[name] = groupState;
            }
            return groupState;
        }

        function setGroupState(name, groupState){
            var tmp = new Object(groupStates);
            tmp[name] = groupState;
            groupStates = tmp;
            stateUpdated(name, groupState);
        }

        function getPreviewWindowMode(deviceId){
            if (typeof(deviceId) != 'string'){
                return undefined;
            } else if (deviceId.length == 0){
                return undefined;
            }
            var mode = previewWindowModes[deviceId];
            if (mode === undefined){
                return 'VIDEO';
            }
            return mode;
        }

        function setPreviewWindowMode(deviceId, mode){
            if (typeof(deviceId) != 'string'){
                return;
            } else if (deviceId.length == 0){
                return;
            }
            if (mode == 'OFF'){
                return;
            }
            if (mode == previewWindowModes[deviceId]){
                return;
            }
            var tmp = new Object(previewWindowModes);
            tmp[deviceId] = mode;
            previewWindowModes = tmp;
        }
    }
}
