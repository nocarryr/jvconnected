
from loguru import logger
import argparse
from typing import List, Dict, ClassVar, Optional, Iterable, Union, Tuple, Sequence
from pathlib import Path
from enum import Flag, auto
import json
import shutil
import subprocess
import shlex
import tempfile
import dataclasses
from dataclasses import dataclass, field

import httpx

from ruamel.yaml import YAML
yaml = YAML(typ='safe')

from jvconnected.ui import get_resource_filename
from jvconnected.ui.tools.qrc_utils import QRCDocument, QRCResource, QRCFile

# BASE_PATH = Path(__file__).parent.parent
RESOURCE_QRC = get_resource_filename('resources.qrc')
RESOURCE_SCRIPT = get_resource_filename('rc_resources.py')
ICON_QML_FILE = get_resource_filename('qml/Fonts/IconFontNames.qml')

RESOURCE_DIR = get_resource_filename('resources')
BASE_PATH = RESOURCE_DIR.parent
FONT_ROOT = RESOURCE_DIR / 'fonts'
ICON_ROOT = RESOURCE_DIR / 'icons'
METADATA_DIR = RESOURCE_DIR / 'fa_metadata'


class FaDownload(object):
    """Context manager to download a fontawesome archive to a temporary directory
    """

    url: str = 'https://use.fontawesome.com/releases/v5.15.2/fontawesome-free-5.15.2-desktop.zip'
    """The url of the archive to download"""

    root: Optional[Path] = None
    """Root of the temporary directory.
    Will be ``None`` until the context is acquired
    """

    archive_file: Optional[Path] = None
    """Path of the archive file once it has been downloaded"""

    archive_dir: Optional[Path] = None
    """The root of the extracted :attr:`archive_file`"""

    def __init__(self, url: Optional[str] = None):
        if url is not None:
            self.url = url

    def __enter__(self):
        self.archive_dir = Path(tempfile.mkdtemp())
        self.archive_file = self.archive_dir / self.url.split('/')[-1]
        logger.debug(f'Downloading fontawesome to {self.archive_file}')
        with httpx.stream('GET', self.url) as r:
            with self.archive_file.open('wb') as fd:
                for chunk in r.iter_bytes():
                    fd.write(chunk)
        self.root = Path(tempfile.mkdtemp())
        logger.debug(f'Unpacking to {self.root}')
        shutil.unpack_archive(self.archive_file, self.root)
        return self.root / self.archive_file.stem

    def __exit__(self, *args):
        if self.root is not None:
            logger.debug(f'Removing {self.root}')
            shutil.rmtree(self.root)
            self.root = None
        if self.archive_file is not None:
            logger.debug(f'Removing {self.archive_file}')
            self.archive_file.unlink()
            self.archive_file = None
        if self.archive_dir is not None:
            logger.debug(f'Removing {self.archive_dir}')
            self.archive_dir.rmdir()
            self.archive_dir = None



class Style(Flag):
    """Flags to indicate which styles are available for :class:`Icon`
    """

    NONE = auto()
    """No value, used as a default"""

    BRANDS = auto()
    """Brands style"""

    REGULAR = auto()
    """Regular style"""

    SOLID = auto()
    """Solid style"""

    ALL = BRANDS | REGULAR | SOLID
    """All styles"""

    @classmethod
    def to_yaml(cls, representer, instance):
        names = []
        for member in cls:
            if member in instance:
                names.append(member.name)
        return representer.represent_scalar(f'!{cls.__name__}', '|'.join(names))

    @classmethod
    def from_yaml(cls, constructor, node):
        style = None
        for name in node.value.split('|'):
            _style = getattr(cls, name)
            if style is None:
                style = _style
            else:
                style |= _style
        if style is None:
            style = Style.NONE
        return style


@dataclass
class Category:
    """Category assigned to :class:`Icon`
    """
    name: str
    """Category name"""

    label: str
    """Category label"""

    icon_names: List[str] = field(default_factory=list)
    """The icon names in the category"""

    icons: Dict[str, 'Icon'] = field(default_factory=dict)
    """Mapping of icon names to :class:`Icon` instances"""

    yaml_tag: ClassVar[str] = '!Category'

    @classmethod
    def to_yaml(cls, representer, instance):
        d = dataclasses.asdict(instance)
        del d['icons']
        return representer.represent_mapping(cls.yaml_tag, d)

    @classmethod
    def from_yaml(cls, constructor, node):
        kw = constructor.construct_mapping(node)
        return cls(**kw)

@dataclass
class Icon:
    """An icon (svg) file
    """
    name: str
    """Icon name"""

    label: str
    """Icon label"""
    code_point: str
    """Unicode value for the icon"""

    styles: Style = Style.NONE
    """Indicates the :class:`styles <Style>` available"""

    category_names: set = field(default_factory=set)
    """Names of :class:`Category` the icon belongs to"""

    # categories: Dict[str, Category] = field(default_factory=dict)

    yaml_tag: ClassVar[str] = '!Icon'

    def add_to_category(self, category: Category):
        """Add the icon to the given :class:`Category`
        """
        self.category_names.add(category.name)
        category.icons[self.name] = self
        # self.categories[category.name] = category

    def iter_styles(self) -> Iterable[Style]:
        for style in Style:
            if style == Style.NONE or style == Style.ALL:
                continue
            if style not in self.styles:
                continue
            yield style

    def get_svgs(self, icon_root: Path, styles: Optional[Style] = None) -> Iterable[Tuple[Style, Path]]:
        """Get icon svg filenames matching the given :class:`Style` flags.

        Arguments:
            icon_root: The directory containing all icon subdirectories
                (``'svgs'`` within the fontawesome root)
            styles: The :class:`Style` flags to filter by.
                If not given, the instance :attr:`styles` will be used.

        Yields
        ------

        style : :class:`Style`
            style flag for the filename
        filename : :class:`pathlib.Path`
            The svg filename within ``icon_root``

        """
        if styles is None:
            styles = self.styles
        for style in self.iter_styles():
            if style not in styles:
                continue
            fn = self.get_svg(icon_root, style)
            yield style, fn

    def get_svg(self, icon_root: Path, style: Style) -> Path:
        """Get the icon svg filename with the given style

        Arguments:
            icon_root: The directory containing all icon subdirectories
                (``'svgs'`` within the fontawesome root)
            style: The style flag

        Raises:
            ValueError: if the given style is invalid (:attr:`Style.NONE` or
                :attr:`Style.ALL`) or the icon is not available in the style

        """
        if style == Style.ALL or style == Style.NONE:
            raise ValueError('Invalid style flag')
        if not style & self.styles:
            raise ValueError(f'Style "{style}" not available for icon')
        return icon_root / style.name.lower() / f'{self.name}.svg'

    def copy_to_icon_dir(self, icon_root: Path, dest: Path, styles: Optional[Style] = None) -> Iterable[Tuple[Style, Path]]:
        """Copy the icon svg file into the given destination, maintaining the
        relative sub-directories

        Arguments:
            icon_root: The directory containing all icon subdirectories
                (``'svgs'`` within the fontawesome root)
            dest: The destination directory
            styles: :class:`Style` flags to include (see :meth:`get_svgs`)

        Yields
        ------

        style : :class:`Style`
            style flag for the filename
        filename : :class:`pathlib.Path`
            The svg filename within ``icon_root``

        """
        for style, src in self.get_svgs(icon_root, styles):
            assert style in self.styles
            pdir = ICON_ROOT / style.name.lower()
            dst = pdir / src.name
            if dst != src or not dst.exists():
                if not pdir.exists():
                    pdir.mkdir(parents=True)
                shutil.copy2(src, dst)
            yield style, dst

    @classmethod
    def to_yaml(cls, representer, instance):
        d = dataclasses.asdict(instance)
        return representer.represent_mapping(cls.yaml_tag, d)

    @classmethod
    def from_yaml(cls, constructor, node):
        kw = constructor.construct_mapping(node)
        return cls(**kw)

yaml.register_class(Style)
yaml.register_class(Category)
yaml.register_class(Icon)

Categories = Dict[str, Category]
Icons = Dict[str, Icon]

def parse_categories(metadata_dir: Path, icons: Dict[str, Icon]) -> Categories:
    """Parse icon categories from the fontawesome metadata

    Arguments:
        metadata_dir: The fontawesome metadata directory
        icons: Mapping of :class:`Icon` instances as provided by :func:`parse_icons`

    Returns:
        Mapping of :attr:`Category.name` to :class:`Category`

    """
    p = metadata_dir / 'categories.yml'
    data = yaml.load(p)
    categories = {}
    for name, d in data.items():
        category = Category(name=name, label=d['label'], icon_names=d['icons'])
        for icon_name in category.icon_names:
            icon = icons[icon_name]
            icon.add_to_category(category)
        categories[name] = category
    return categories

def parse_icons(metadata_dir: Path) -> Icons:
    """Parse icons from the fontawesome metadata

    Arguments:
        metadata_dir: The fontawesome metadata directory

    Returns:
        Mapping of :attr:`Icon.name` to :class:`Icon`

    """
    p = metadata_dir / 'icons.yml'
    data = yaml.load(p)
    icons = {}
    for icon_name, d in data.items():
        icon = Icon(name=icon_name, label=d['label'], code_point=d['unicode'])
        for st_name in d['styles']:
            icon.styles |= getattr(Style, st_name.upper())
        icons[icon.name] = icon
    return icons

def parse_all(metadata_dir: Path) -> Tuple[Icons, Categories]:
    """Parse icons and categories using :func:`parse_icons` and :func:`parse_categories`

    Arguments:
        metadata_dir: The fontawesome metadata directory

    Returns
    -------

    icons
        The parsed icons
    categories
        The parsed categories

    """
    logger.debug('parsing metadata')

    icons = parse_icons(metadata_dir)
    categories = parse_categories(metadata_dir, icons)
    return icons, categories

def build_qml_names(icons: Icons, outfile: Path = ICON_QML_FILE, qtquick_version: str = '2.15'):
    """Generate a qml document mapping icon names to their :attr:`Icon.code_point`
    """
    def dash_to_camel(s: str) -> str:
        s = s.lower()
        parts = s.split('-')
        parts = ''.join([part.title() for part in parts])
        return f'fa{parts}'

    lines = [
        'pragma Singleton',
        f'import QtQuick {qtquick_version}',
        '',
        'QtObject {',
        '    id: root',
    ]
    style_lines = {}

    for icon in icons.values():
        name = dash_to_camel(icon.name)
        prop_line = f'readonly property string {name}: "\\u{icon.code_point}"'
        for style in icon.iter_styles():
            style_name = style.name.lower()
            _lines = style_lines.get(style_name)
            if _lines is None:
                _lines = [
                    '    readonly property QtObject %s: QtObject {' % (style_name),
                    f'        id: {style_name}Obj',
                    f'        readonly property string name: "{style_name}"',
                ]
                style_lines[style_name] = _lines
            _lines.append(f'        {prop_line}')
    for _lines in style_lines.values():
        _lines.append('    }')
        lines.extend(_lines)
    lines.extend(['}', ''])
    outfile.write_text('\n'.join(lines))

@logger.catch
def build_theme(fa_root: Path, theme_name: str, category_names: Optional[Sequence[str]] = None):
    """Copy and process fontawesome resources and prep them for the Qt Resouce System

    Arguments:
        fa_root: Root directory of the unpacked fontawesome archive
            (:attr:`FaDownload.archive_dir`)
        theme_name: The name of the `icon theme`_ to generate formatted according
            to the `freedesktop specification`_
        category_names: A list of fontawesome categories to include. If not provided,
            use all available categories.

    .. _icon theme: https://doc.qt.io/qt-5.15/qtquickcontrols2-icons.html#icon-themes
    .. _freedesktop specification: http://standards.freedesktop.org/icon-theme-spec/icon-theme-spec-latest.html

    """
    theme_root = RESOURCE_DIR
    metadata_src_dir = fa_root / 'metadata'
    icon_src_dir = fa_root / 'svgs'
    theme_root.mkdir(parents=True, exist_ok=True)
    icon_style = Style.ALL
    all_icons, all_categories = parse_all(metadata_src_dir)

    if category_names is not None:
        category_names = set(category_names)
    # if category_names is None:
    #     categories = all_categories
    # else:
    #     categories = {name:all_categories[name] for name in category_names}

    all_dirs = set()
    all_files = set()

    for license_file in fa_root.glob('LICENSE*'):
        dst = RESOURCE_DIR / license_file.name
        logger.debug(f'{license_file} -> {dst}')
        shutil.copy2(license_file, dst)

    if not METADATA_DIR.exists():
        METADATA_DIR.mkdir()
    if METADATA_DIR != metadata_src_dir:
        for meta_src in metadata_src_dir.iterdir():
            meta_dst = METADATA_DIR / meta_src.name
            logger.debug(f'{meta_src} -> {meta_dst}')
            shutil.copy2(meta_src, meta_dst)


    qrc_doc = QRCDocument.create(base_path=BASE_PATH)

    icon_resources = {}

    logger.debug('copying svgs')

    no_categories = {}

    for icon in all_icons.values():
        if category_names is not None:
            matched_categories = category_names & icon.category_names
            if not len(matched_categories):
                continue
        # if not len(icon.category_names):
        #     no_categories[icon.name] = icon
        # matched_categories = set(categories.keys()) & icon.category_names
        # if not len(matched_categories):
        #     continue
        for style, p in icon.copy_to_icon_dir(icon_src_dir, icon_style):
            assert style != Style.ALL
            if p in all_files:
                continue
            style_name = style.name.lower()
            resource = icon_resources.get(style_name)
            if resource is None:
                resource = qrc_doc.add_child(
                    tag='qresource',
                    prefix=f'/icons/{style_name}',
                )
                icon_resources[style_name] = resource
            all_files.add(p)
            resource.add_file(p, alias=p.name)

    print('\n'.join(no_categories.keys()))

    logger.debug(f'icon_resources: {icon_resources}')

    # Build index.theme

    lines = [
        '[Icon Theme]',
        f'Name={theme_name}',
        'Directories={}'.format(','.join(icon_resources.keys())),
        '',
    ]
    for style_name, resource in icon_resources.items():
        lines.extend([
            f'[{style_name}]',
            'Size=48',
            'Type=Scalable',
            'MinSize=8',
            'MaxSize=512',
            'Context=Applications',
            '',
        ])

    theme_file = ICON_ROOT / 'index.theme'
    theme_file.write_text('\n'.join(lines))

    resource = qrc_doc.add_child(tag='qresource', prefix='/icons')
    resource.add_file(theme_file, alias=theme_file.name)

    # Copy fonts

    logger.debug('copying fonts')
    qrc_resource = qrc_doc.add_child(tag='qresource', prefix='/fonts')
    # fonts_src = fa_root / 'webfonts'
    fonts_src = fa_root / 'otfs'

    for font_src in fonts_src.iterdir():
        if font_src.suffix != '.otf':
            continue
        font_dst = FONT_ROOT / font_src.name
        if not font_dst.parent.exists():
            font_dst.parent.mkdir(parents=True)
        shutil.copy2(font_src, font_dst)
        qrc_resource.add_file(font_dst, alias=font_dst.name)


    # Build name/unicode map

    icon_code_points = {}
    for icon in all_icons.values():
        icon_code_points[icon.name] = icon.code_point

    icon_map_file = FONT_ROOT / 'name-map.json'
    icon_map_file.write_text(json.dumps(icon_code_points))
    qrc_resource.add_file(icon_map_file, alias=icon_map_file.name)

    # Generate qml definition file

    build_qml_names(all_icons)


    qrc_doc.write(RESOURCE_QRC)

def build_rcc():
    cmd_str = f'pyside2-rcc -o {RESOURCE_SCRIPT} {RESOURCE_QRC}'
    logger.debug(cmd_str)
    subprocess.call(shlex.split(cmd_str))

@logger.catch
def main(**kwargs):
    rcc_only = kwargs.get('rcc_only', False)

    if rcc_only:
        qrc_file = QRCDocument.from_file(RESOURCE_QRC)
    else:
        with FaDownload() as fa_root:
            qrc_file = build_theme(fa_root, 'fa-icons')
    build_rcc()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    # p.add_argument('-d', '--download', dest='download', action='store_true')
    p.add_argument('-r', '--rcc-only', dest='rcc_only', action='store_true')

    args = p.parse_args()
    main(**vars(args))
