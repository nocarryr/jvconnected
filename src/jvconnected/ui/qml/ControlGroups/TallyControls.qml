import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import QtQuick.Controls.Fusion 2.15
import QtQuick.Controls.Fusion.impl 2.15

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
        horizontalPadding: 8
        // enabled: false
        checkable: true
        checked: root.model.tally.program
        palette.button: checked ? '#e00000' : '#500000'
        palette.buttonText: '#202020'
        onToggled: {
            root.model.tally.setProgram(checked);
        }
        background: ButtonPanel {
            implicitWidth: 20
            implicitHeight: 20

            control: pgmTallyBtn
            visible: true//control.down || control.checked || control.highlighted || control.visualFocus || control.hovered
        }
    }
    ToolButton {
        id: pvwTallyBtn
        text: 'PVW'
        horizontalPadding: 8
        // enabled: false
        checkable: true
        palette.button: checked ? '#00e000' : '#004500'
        palette.buttonText: '#202020'
        checked: root.model.tally.preview
        onToggled: {
            root.model.tally.setPreview(checked);
        }
        background: ButtonPanel {
            implicitWidth: 20
            implicitHeight: 20

            control: pvwTallyBtn
            visible: true//control.down || control.checked || control.highlighted || control.visualFocus || control.hovered
        }
    }
}
