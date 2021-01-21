import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Fonts 1.0

MyGroupBox {
    id: root

    property bool isCollapsed: state == 'collapsed'

    states: [
        State {
            name: 'collapsed'
            PropertyChanges {
                target: root
                transformYScale: 0
            }
            PropertyChanges {
                target: root.container
                visible: false
            }
        },
        State {
            name: 'expanded'
            PropertyChanges {
                target: root
                transformYScale: 1
            }
            PropertyChanges {
                target: root.container
                visible: true
            }
        }
    ]

    transitions: [
        Transition {
            from: 'collapsed'
            to: 'expanded'
            SequentialAnimation {
                PropertyAnimation {
                    target: root.container
                    properties: 'visible'
                    duration: 0
                }
                NumberAnimation {
                    target:root
                    properties:'transformYScale'
                }
            }
        },
        Transition {
            from: 'expanded'
            to: 'collapsed'
            SequentialAnimation {
                NumberAnimation {
                    target:root
                    properties:'transformYScale'
                }
                PropertyAnimation {
                    target:root.container
                    properties:'visible'
                    duration: 0
                }
            }
        }
    ]

    state: 'collapsed'
    property real transformYScale: 1
    property Scale containerTransform: Scale {
        yScale: transformYScale
    }

    Component.onCompleted: {
        root.container.transform = root.containerTransform;
    }

    // header: HeaderLabel {
    //     id: lbl
    //     // anchors.fill: parent
    //     text: root.title
    // }

    function toggleCollapsed(){
        setCollapsed(!root.isCollapsed);
    }
    function setCollapsed(state){
        if (state){
            root.state = 'collapsed';
        } else {
            root.state = 'expanded';
        }
    }

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            ToolButton {
                z: 10
                id: toggleBtn
                property IconFont iconFont: IconFont {
                    iconName: root.isCollapsed ? 'faCaretRight' : 'faCaretDown'
                }
                text: iconFont.text
                font: iconFont.iconFont
                onClicked: { root.toggleCollapsed() }
            }
            Label {
                z: 8
                text: root.title
                elide: Label.ElideRight
                horizontalAlignment: Qt.AlignHCenter
                verticalAlignment: Qt.AlignVCenter
                Layout.fillWidth: true
            }
            Item { z:8; implicitWidth: toggleBtn.implicitWidth }
        }
        MouseArea {
            z: 9
            anchors.fill: parent
            // cursorShape: Qt.PointingHandCursor
            hoverEnabled: false
            onClicked: {
                root.toggleCollapsed();
                toggleBtn.checked = root.isCollapsed;
            }
        }
    }

}
