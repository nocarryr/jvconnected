import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Controls 1.0
import Fonts 1.0

GridLayout {
    id: root

    property CameraModel model

    columns: 3
    rows: 2
    Item {
        Layout.fillWidth: true
        Layout.rowSpan: 2
    }
    Label {
        text: root.model.battery.batteryState == 'ON_BATTERY' ? root.model.battery.textStatus : ''
        horizontalAlignment: Text.AlignHCenter
        Layout.alignment: Qt.AlignVCenter | Qt.AlignHCenter
        font.pointSize: 9
        Layout.columnSpan: 2
    }
    Label {
        property IconFont iconFont: IconFont {
            pointSize: 12
            iconName: root.model.battery.batteryState == 'ON_BATTERY' ? 'faCarBattery' :
                      root.model.battery.batteryState == 'CHARGING' ? 'faChargingStation' :
                      root.model.battery.batteryState == 'CHARGED'? 'faPlug' : 'faPlug'
        }
        text: iconFont.text
        font: iconFont.iconFont
        color: palette.buttonText
    }
    Label {
        property IconFont iconFont: IconFont {
            pointSize: 12
            iconName: root.model.battery.level <= .1 ? 'faBatteryEmpty' :
                      root.model.battery.level <= .25 ? 'faBatteryQuarter' :
                      root.model.battery.level <= .5 ? 'faBatteryHalf' :
                      root.model.battery.level <= .75 ? 'faBatteryThreeQuarters' : 'faBatteryFull'
        }
        text: iconFont.text
        font: iconFont.iconFont
        color: root.model.battery.batteryState == 'ON_BATTERY' ?
              (root.model.battery.level >= .5 ? '#21be21' : '#d6c31e') : palette.buttonText
    }
}
