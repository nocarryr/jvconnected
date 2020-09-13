from typing import List, Dict, ClassVar, Optional, Iterator
from pathlib import Path
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

class QRCElement(object):
    """An element within a QRC document tree

    Attributes:
        parent (QRCElement, optional): The parent element. If this element is
            the document root, this is ``None``
        element (ET.Element): The :class:`xml.etree.ElementTree.Element`
            associated with this element
        children (List[QRCElement]): Direct descendants of this element

    """

    TAG: ClassVar[Optional[str]] = None
    """The default tag name"""

    def __init__(self, **kwargs):
        parent = kwargs.get('parent')
        element = kwargs.get('element')
        tag = kwargs.get('tag', self.TAG)
        attrib = kwargs.get('attrib', {})
        if element is None:
            assert tag is not None
            if parent is None:
                element = ET.Element(tag, attrib)
            else:
                element = ET.SubElement(parent.element, tag, attrib)
        self.parent = parent
        self.element = element
        self.children = []
        for child_elem in element:
            self.add_child(element=child_elem)

    def tostring(self) -> str:
        """Build the XML representation of the tree
        """
        ugly = ET.tostring(self.element, encoding='unicode')
        dom = minidom.parseString(ugly)
        pretty = dom.toprettyxml()
        pretty = [line for line in pretty.splitlines() if len(line.strip('\t'))]
        pretty[0] = '<!DOCTYPE RCC>'
        pretty[1] = '<RCC version="1.0">'
        return '\n'.join(pretty)

    def write(self, filename: Path):
        """Save the contents of :meth:`tostring` as a QRC file

        Note:
            This may only be called on the root element

        """
        assert self.parent is None
        filename.write_text(self.tostring())

    @classmethod
    def create(cls, **kwargs) -> 'QRCElement':
        """Create an instance of :class:`QRCElement`

        The subclass will be chosen using the given element or tag keyword arguments

        Keyword Arguments:
            element (ET.Element, optional): If provided, an instance of
                :class:`xml.etree.ElementTree.Element` to use as the root element
            tag (str, optional): If no element is provided, this will be the tag
                name of the root element. If both ``element`` and ``tag`` are ``None``,
                the :attr:`TAG` attribute of the class will be used.

        """
        element = kwargs.get('element')
        if element is not None:
            tag = element.tag
        else:
            tag = kwargs.get('tag', cls.TAG)
        _cls = cls.cls_for_tag(tag)
        return _cls(**kwargs)

    @classmethod
    def cls_for_tag(cls, tag: str):
        """Find a subclass of :class:`QRCElement` matching the given tag
        """
        def iter_subclass(_cls):
            yield _cls
            for subcls in _cls.__subclasses__():
                if not issubclass(subcls, QRCElement):
                    continue
                yield subcls
        for _cls in iter_subclass(QRCElement):
            if _cls.TAG == tag:
                return _cls

    @property
    def root_element(self) -> 'QRCElement':
        """The root of the tree
        """
        p = self.parent
        if p is None:
            return self
        return p.root_element

    @property
    def tag(self) -> str:
        """The :attr:`~xml.etree.ElementTree.Element.tag` name of the element
        """
        return self.element.tag

    @property
    def attrib(self) -> Dict:
        """The element :attr:`attributes <xml.etree.ElementTree.Element.attrib>`
        """
        return self.element.attrib

    @property
    def text(self):
        """The element :attr:`~xml.etree.ElementTree.Element.text`
        """
        return self.element.text
    @text.setter
    def text(self, value):
        self.element.text = value

    def add_child(self, **kwargs) -> 'QRCElement':
        """Create a child instance using :meth:`create` and add it to this
        element's :attr:`children`

        """
        kwargs['parent'] = self
        child = self.create(**kwargs)
        self.children.append(child)
        return child

    def walk(self) -> Iterator['QRCElement']:
        """Iterate over this element and all of its descendants
        """
        yield self
        for c in self.children:
            yield from c.walk()

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'
    def __str__(self):
        return self.tag

class QRCDocument(QRCElement):
    """A :class:`QRCElement` subclass to be used as the document root

    Keyword Arguments:
        base_path (pathlib.Path): The filesystem path representing the root
            directory for the document (usually the document's directory)

    """

    TAG: ClassVar[str] = 'RCC'
    """The default tag name"""

    def __init__(self, **kwargs):
        self.base_path = kwargs['base_path']
        super().__init__(**kwargs)

    @classmethod
    def from_file(cls, filename: Path) -> 'QRCDocument':
        """Create a tree from an existing qrc file
        """
        root = ET.fromstring(filename.read_text())
        return cls(element=root, base_path=filename.resolve().parent)

    def search_for_file(self, filename: Path) -> Optional['QRCFile']:
        """Search for the :class:`QRCFile` element matching the given filename
        """
        for c in self.children:
            if not isinstance(c, QRCResource):
                continue
            r = c.search_for_file(filename)
            if r is not None:
                return r


class QRCResource(QRCElement):
    """A :class:`QRCElement` subclass representing a qresource element
    """

    TAG: ClassVar[str] = 'qresource'
    """The default tag name"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'prefix' in kwargs:
            self.prefix = kwargs['prefix']

    @property
    def prefix(self):
        """The directory prefix used for all children of this element
        """
        return self.attrib.get('prefix')
    @prefix.setter
    def prefix(self, value: str):
        self.attrib['prefix'] = value

    @property
    def path(self) -> Path:
        """The filesystem location for this element given the :attr:`~QRCDocument.base_path`
        of the :attr:`root_element` and :attr:`prefix`
        """
        root = self.root_element
        p = root.base_path
        if self.prefix and self.prefix != '/':
            p = p / self.prefix.lstrip('/')
        return p

    def search_for_file(self, filename: Path) -> Optional['QRCFile']:
        """Search within this qresource for the :class:`QRCFile` element
        matching the given filename
        """
        base_path = self.path
        for c in self.children:
            if not isinstance(c, QRCFile):
                continue
            if filename == base_path / c.filename:
                return c

class QRCFile(QRCElement):
    """A :class:`QRCElement` subclass representing a file resource
    """

    TAG: ClassVar[str] = 'file'
    """The default tag name"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for attr in ['filename', 'alias']:
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])

    @property
    def filename(self) -> Path:
        """The filename as a :class:`pathlib.Path`
        """
        s = self.text
        if s is None:
            return None
        s = s.strip()
        if not len(s):
            return None
        return Path(s)
    @filename.setter
    def filename(self, value):
        if value is None:
            self.text = None
        else:
            if not isinstance(value, Path):
                value = Path(value)
            self.text = str(value)

    @property
    def alias(self) -> Optional[str]:
        """The file alias as described in the `qrc documentation`_

        .. _qrc documentation: https://doc.qt.io/qt-5/resources.html#resource-collection-files-op-op-qrc
        """
        return self.attrib.get('alias')
    @alias.setter
    def alias(self, value):
        if isinstance(value, Path):
            value = str(value)
        self.attrib['alias'] = value
