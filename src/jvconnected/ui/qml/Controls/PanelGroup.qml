import QtQuick 2.15

CollapseGroupBox {
    id: root
    property string groupName
    onGroupNameChanged: {
        var gstate = UiState.panelGroups.getGroupState(root.groupName);
        root.state = gstate;
    }
    onStateChangeTriggered: {
        if (groupName !== undefined){
            UiState.panelGroups.setGroupState(root.groupName, newState);
        }
    }
    Connections {
        target: UiState.panelGroups
        function onStateUpdated(name, newState){
            if (name != root.groupName){
                return;
            }
            root.state = newState;
        }
    }
    Component.onCompleted: {
        var gstate;
        if (root.groupName !== undefined){
            gstate = UiState.panelGroups.getGroupState(root.groupName);
            root.state = gstate;
        }
    }
}
