import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0

RowLayout {
    id: root

    property CameraModel model

    Label {
        text: 'Tally Status'
    }
    Item { Layout.fillWidth: true }
    ToolButton {
        id: pgmTallyBtn
        text: 'PGM'
        // enabled: false
        checkable: true
        checked: root.model.tally.program
        onToggled: {
            root.model.tally.setProgram(checked);
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
        checked: root.model.tally.preview
        onToggled: {
            root.model.tally.setPreview(checked);
        }
        background: Rectangle {
            implicitWidth: 80
            implicitHeight: 40
            color: pvwTallyBtn.checked ? '#00ff00' : '#008000'
            border.color: pvwTallyBtn.palette.highlight
        }
    }
}
