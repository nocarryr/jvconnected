import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Frame {
    id: root
    property string title
    property alias header: hdr.contentItem
    property alias content: container.contentItem
    property Item container: container
    property alias headerFont: lbl.font
    property alias headerBackgroundColor: lbl.backgroundColor
    property alias headerTextColor: lbl.textColor

    spacing: 6
    topPadding: 0

    implicitWidth: col.implicitWidth + leftPadding + rightPadding
    implicitHeight: col.implicitHeight + topPadding + bottomPadding

    contentItem: ColumnLayout {
        id: col
        implicitWidth: Math.max(hdr.implicitWidth, container.implicitWidth) + leftPadding + rightPadding
        implicitHeight: hdr.implicitHeight + container.implicitHeight + spacing + topPadding + bottomPadding
        // anchors.fill: parent
        spacing: root.spacing
        Control {
            id: hdr
            Layout.fillWidth: true
            padding: 0
            contentItem: HeaderLabel {
                id: lbl
                // anchors.fill: parent
                text: root.title
            }
        }
        Control {
            id:container
            Layout.fillWidth: true
        }
    }
}
