import QtQuick 2.15
import QtQuick.Controls 2.15

TabBar {
    id: control
    // spacing: 8
    property real maxItemWidth: 1

    function updateMaxItemWidth(){
        var children = control.contentChildren,
            maxW = control.maxItemWidth,
            child;
        for (var i=0;i<children.length;i++){
            child = children[i];
            if (child.implicitWidth > maxW){
                maxW = child.implicitWidth;
            }
        }
        control.maxItemWidth = maxW;
    }

    Component.onCompleted: {
        updateMaxItemWidth();
    }
}
