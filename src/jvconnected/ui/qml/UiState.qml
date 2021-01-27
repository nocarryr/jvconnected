pragma Singleton

import QtQuick 2.15
import Qt.labs.settings 1.0

QtObject {
    id: root
    property string foo: 'bar'

    property QtObject panelGroups: QtObject {
        id: panelGroupsObj
        property var groupStates: ({})

        signal stateUpdated(string name, string newState)

        property Settings settings: Settings {
            category: "PanelGroups"
            property alias groupStates: panelGroupsObj.groupStates
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
    }
}
