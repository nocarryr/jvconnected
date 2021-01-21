import QtQuick 2.15

QtObject {
    id: root
    property QtObject iconNames: IconFontNames.solid
    property font iconFont: Qt.font({
        family: IconFonts.solid,
        styleName: 'Solid',
        pointSize: 16,
    })
    property string currentStyle: 'solid'

    onCurrentStyleChanged: {
        root.iconFont.family = getStyleName(currentStyle);
        root.iconFont.styleName = currentStyle[0].toUpperCase() + currentStyle.slice(1);
        // console.log(root.text, root.iconFont.styleName);
        root.iconNames = getIconNamespace(currentStyle);
    }

    function getStyleName(styleName){
        if (styleName == 'solid'){
            return IconFonts.solid;
        } else if (styleName == 'regular'){
            return IconFonts.regular;
        } else if (styleName == 'brands'){
            return IconFonts.brands;
        }
    }

    function getIconNamespace(styleName){
        if (styleName == 'solid'){
            return IconFontNames.solid;
        } else if (styleName == 'regular'){
            return IconFontNames.regular;
        } else if (styleName == 'brands'){
            return IconFontNames.brands;
        }
    }

    property string iconName
    property string text: ''

    onIconNameChanged: {
        if (!iconName.includes('fa')){
            return;
        }
        var d = findIconName(iconName);
        // console.log(JSON.stringify({'text':d.text, 'styleName':d.styleName, 'nameSpace':d.nameSpace.name}));
        if (d.nameSpace.name != root.currentStyle){
            root.currentStyle = d.nameSpace.name;
        }
        root.text = d.text;
    }

    function findIconName(name){
        var nameSpace = root.iconNames,
            txt = nameSpace[name],
            allStyleNames = ['solid', 'regular', 'brands'],
            i = allStyleNames.indexOf(root.currentStyle);
        // allStyleNames.delete(root.currentStyle);
        delete allStyleNames[i];
        if (txt !== undefined){
            return {'text':txt, 'styleName':root.currentStyle, 'nameSpace':nameSpace};
        }
        for (let styleName of allStyleNames){
            nameSpace = getIconNamespace(styleName);
            txt = nameSpace[name];
            if (txt !== undefined){
                return {'text':txt, 'styleName':styleName, 'nameSpace':nameSpace};
            }
        }
    }

}
