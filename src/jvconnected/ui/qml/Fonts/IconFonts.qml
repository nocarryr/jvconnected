pragma Singleton

import QtQuick 2.15

QtObject {
    id: root

    readonly property FontLoader regularLdr: FontLoader {
        source: 'qrc:///fonts/Font Awesome 5 Free-Regular-400.otf'
    }
    readonly property FontLoader solidLdr: FontLoader {
        source: 'qrc:///fonts/Font Awesome 5 Free-Solid-900.otf'
    }
    readonly property FontLoader brandsLdr: FontLoader {
        source: 'qrc:///fonts/Font Awesome 5 Brands-Regular-400.otf'
    }

    property alias brands: root.brandsLdr.name
    property alias solid: root.solidLdr.name
    property alias regular: root.regularLdr.name
}
