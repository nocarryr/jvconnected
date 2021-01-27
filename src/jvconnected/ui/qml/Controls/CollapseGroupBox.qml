import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtQuick.Controls.Fusion 2.15
import QtQuick.Controls.Fusion.impl 2.15
import Fonts 1.0

MyGroupBox {
    id: root

    property bool isCollapsed: state == 'collapsed'
    signal stateChangeTriggered(string newState)

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
        id: hdr
        position: ToolBar.Header
        property bool flat: false
        property bool highlighted: false
        contentHeight: Math.max(toggleBtn.implicitHeight, lbl.implicitHeight)
        contentWidth: (toggleBtn.implicitWidth * 2) + lbl.implicitWidth + row.spacing
        RowLayout {
            id: row
            anchors.fill: parent
            ToolButton {
                z: 10
                id: toggleBtn
                property IconFont iconFont: IconFont {
                    iconName: root.isCollapsed ? 'faCaretRight' : 'faCaretDown'
                }
                text: iconFont.text
                font: iconFont.iconFont
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                onClicked: { root.toggleCollapsed() }
                background: Rectangle {
                    color: 'transparent'
                }
            }
            Label {
                id: lbl
                z: 8
                text: root.title
                elide: Label.ElideRight
                horizontalAlignment: Qt.AlignHCenter
                verticalAlignment: Qt.AlignVCenter
                Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
                Layout.fillWidth: true
            }
            Item { id:filler; z:8; implicitWidth: toggleBtn.implicitWidth }
        }
        MouseArea {
            id: mse
            z: 9
            anchors.fill: parent
            // cursorShape: Qt.PointingHandCursor
            hoverEnabled: false
            onClicked: {
                root.toggleCollapsed();
                root.stateChangeTriggered(root.state);
                toggleBtn.checked = root.isCollapsed;
            }
        }
        background: ButtonPanel {
            implicitWidth: 20
            implicitHeight: 20

            control: hdr
            // visible: toggleBtn.down || toggleBtn.checked || toggleBtn.highlighted || toggleBtn.visualFocus || mse.hovered
        }
    }
}
