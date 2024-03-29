import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import Qt.labs.settings 1.0
import DeviceModels 1.0
import Controls 1.0

QtObject {
    id: root
    property DeviceModel device
    property int deviceIndex: device ? device.deviceIndex : -1
    property string deviceId: device ? device.deviceId : ''

    function setDeviceIndex(value){
        device.setDeviceIndex(value);
    }

    property CameraParamsModel cameraParams: CameraParamsModel { device: root.device }
    property NTPParamsModel ntpParams: NTPParamsModel { device: root.device }
    property BatteryParamsModel battery: BatteryParamsModel { device: root.device }
    property IrisModel iris: IrisModel { device: root.device }
    property GainModeModel gainMode: GainModeModel { device: root.device }
    property GainValueModel gainValue: GainValueModel { device: root.device }
    property MasterBlackModel masterBlack: MasterBlackModel { device: root.device }
    property MasterBlackPosModel masterBlackPos: MasterBlackPosModel { device: root.device }
    property FocusModeModel focusMode: FocusModeModel { device: root.device }
    property FocusPosModel focusPos: FocusPosModel { device: root.device }
    property ZoomPosModel zoomPos: ZoomPosModel { device: root.device }
    property DetailModel detail: DetailModel { device: root.device }
    property QtObject paint: QtObject {
        property WbModeModel mode: WbModeModel { device: root.device }
        property WbColorTempModel colorTemp: WbColorTempModel { device: root.device }
        property WbRedPaintModel redPaint: WbRedPaintModel { device: root.device }
        property WbBluePaintModel bluePaint: WbBluePaintModel { device: root.device }
    }
    property TallyModel tally: TallyModel { device: root.device }
}
