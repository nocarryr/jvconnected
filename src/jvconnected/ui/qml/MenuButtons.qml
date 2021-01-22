import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import Fonts 1.0

Control {
    id: root

    property bool menuActive: false
    property real itemWidth: 100//fontMetrics.advanceWidth('Cancel') + 20

    signal clicked(string buttonType)

    contentItem: GridLayout {
        id: grid
        columns: 3
        rows: 3

        ArrowButton {
            direction: Qt.UpArrow
            enabled: root.menuActive
            round: false
            Layout.row: 0
            Layout.column: 1
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Up') }
        }

        ArrowButton {
            direction: Qt.DownArrow
            enabled: root.menuActive
            round: false
            Layout.row: 2
            Layout.column: 1
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Down') }
        }

        ArrowButton {
            direction: Qt.LeftArrow
            enabled: root.menuActive
            round: false
            Layout.row: 1
            Layout.column: 0
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Left') }
        }

        ArrowButton {
            direction: Qt.RightArrow
            enabled: root.menuActive
            round: false
            Layout.row: 1
            Layout.column: 2
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Right') }
        }

        RoundButton {
            // text: 'Menu'
            // text: "\uf142"
            // font.family: IconFonts.icons
            // font.pointSize: 12
            property IconFont iconFont: IconFont {
                iconName: 'faBars'
            }
            text: iconFont.text
            font: iconFont.iconFont
            // font.bold: root.menuActive
            radius: 0
            Layout.row: 0
            Layout.column: 0
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Menu') }
        }

        RoundButton {
            property IconFont iconFont: IconFont {
                iconName: 'faWindowClose'
            }
            text: iconFont.text
            font: iconFont.iconFont
            radius: 0
            Layout.row: 2
            Layout.column: 0
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Cancel') }
        }

        RoundButton {
            enabled: root.menuActive
            property IconFont iconFont: IconFont {
                iconName: 'faCheckSquare'
            }
            text: iconFont.text
            font: iconFont.iconFont
            radius: 0
            Layout.row: 1
            Layout.column: 1
            Layout.fillWidth: true
            implicitWidth: root.itemWidth
            onClicked: { root.clicked('Set') }
        }
    }
}
