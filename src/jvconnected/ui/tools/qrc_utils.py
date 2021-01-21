from typing import List, Dict, ClassVar, Optional, Iterator
from pathlib import Path
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import hashlib

HASH_ALGO = 'sha1'
"""The :mod:`hashlib` algorithm to use for creating file hashes
"""

HASH_FUNC = getattr(hashlib, HASH_ALGO)

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

    def remove_child(self, child: 'QRCElement'):
        """Remove an child element the tree
        """
        self.element.remove(child.element)
        self.children.remove(child)

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

    @property
    def current_hash(self) -> Optional[str]:
        """The hash of the contents when the qrc file was last saved
        """
        return self.attrib.get('content_hash')
    @current_hash.setter
    def current_hash(self, value: str):
        self.attrib['content_hash'] = value

    def hashes_match(self) -> bool:
        """Determine if the contents defined within the document have changed
        on the local filesystem

        Compares the :attr:`current_hash` against the result of :meth:`hash_contents`
        """
        if not self.current_hash:
            return False
        local_hash = self.hash_contents()
        return local_hash == self.current_hash

    def add_file(self, filename: Path, prefix: Optional[str] = None, **kwargs) -> 'QRCFile':
        """Add a :class:`QRCFile` to the document if it does not currently exist

        Arguments:
            filename (pathlib.Path): The filename to add
            prefix (str, optional): The :attr:`~QRCResource.prefix` to use for
                the :class:`QRCResource`. If not given, it will default to ``"/"``
            **kwargs: Extra keyword arguments to pass to the :class:`QRCFile` creation

        """
        if prefix is None:
            prefix = '/'
        resource_el = self.find_resource(prefix)
        if resource_el is None:
            resource_el = self.add_child(tag='qresource', prefix=prefix)
        return resource_el.add_file(filename, **kwargs)

    def find_resource(self, prefix: str) -> Optional['QRCResource']:
        """Search for a :class:`QRCResource` matching the given prefix

        If one is not found, ``None`` will be returned
        """
        for el in self.children:
            if el.prefix == prefix:
                return el

    def search_for_file(self, filename: Path) -> Optional['QRCFile']:
        """Search for the :class:`QRCFile` element matching the given filename
        """
        for c in self.children:
            if not isinstance(c, QRCResource):
                continue
            r = c.search_for_file(filename)
            if r is not None:
                return r

    def remove_missing_files(self) -> List['QRCFile']:
        """Find and remove any :class:`QRCFile` elements whose filenames do not
        currently exist in the filesystem.

        The elements that were removed (if any) are returned
        """
        removed = []
        for f in self.iter_files():
            if not f.exists():
                removed.append(f)
                f.parent.remove_child(f)
        return removed

    def iter_resources(self) -> Iterator['QRCResource']:
        """Iterate over child :class:`QRCResource` instances
        """
        for c in self.children:
            if isinstance(c, QRCResource):
                yield c

    def iter_files(self) -> Iterator['QRCFile']:
        """Iterate through all :class:`QRCFile` instances in the tree
        """
        for r in self.iter_resources():
            yield from r.iter_files()

    def hash_contents(self) -> str:
        """Create a single hash from all :class:`QRCFile` data on the local
        filesystem using :meth:`QRCFile.hash_contents`
        """
        hashes = [f.hash_contents() for f in self.iter_files()]
        m = HASH_FUNC()
        for hval in sorted(hashes):
            m.update(hval.encode('utf-8'))
        return m.hexdigest()

    def tostring(self) -> str:
        self.current_hash = self.hash_contents()
        return super().tostring()


class QRCResource(QRCElement):
    """A :class:`QRCElement` subclass representing a qresource element
    """

    TAG: ClassVar[str] = 'qresource'
    """The default tag name"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._path = None
        if 'prefix' in kwargs:
            self.prefix = kwargs['prefix']

    @property
    def prefix(self):
        """The prefix to be used for all children of this ``qresource``.

        This only affects the way the child resources are accessed from within
        the Qt Resource System and has no impact on local file paths.
        """
        return self.attrib.get('prefix')
    @prefix.setter
    def prefix(self, value: str):
        self.attrib['prefix'] = value

    @property
    def path(self) -> Path:
        """Alias for :attr:`~QRCDocument.base_path` of the :attr:`root_element`
        """
        return self.root_element.base_path

    def add_file(self, filename: Path, **kwargs) -> 'QRCFile':
        """Add a :class:`QRCFile` to the resource if it does not currently exist

        Arguments:
            filename (pathlib.Path): The filename to add
            **kwargs: Extra keyword arguments to pass to the :class:`QRCFile` creation

        """
        el = self.search_for_file(filename)
        if el is not None:
            return el

        rel_fn = filename.resolve().relative_to(self.path.resolve())
        kw = kwargs.copy()
        kw['tag'] = 'file'
        kw['filename'] = rel_fn
        return self.add_child(**kw)

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

    def iter_files(self) -> Iterator['QRCFile']:
        """Iterate over all :class:`QRCFile` instances within this qresource
        """
        for c in self.children:
            if isinstance(c, QRCFile):
                yield c

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
        (relative to the parent :class:`QRCResource`)
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
    def filename_abs(self) -> Path:
        """Filename including the parent :attr:`QRCResource.path`
        """
        base = self.parent.path
        return base / self.filename

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

    def exists(self) -> bool:
        """Returns whether the file exists in the filesystem
        """
        return self.filename_abs.exists()

    def hash_contents(self) -> str:
        """Create a hash of the file data using :mod:`hashlib` algorithm defined
        by :any:`HASH_ALGO`
        """
        m = HASH_FUNC()
        block_size = 65536
        p = self.filename_abs
        if not p.exists():
            return m.hexdigest()

        with open(p, 'rb') as fp:
            while True:
                data = fp.read(block_size)
                if not data:
                    break
                m.update(data)
        return m.hexdigest()
