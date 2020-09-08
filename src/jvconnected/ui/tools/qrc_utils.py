from pathlib import Path
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

class QRCElement(object):
    TAG = None
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

    def tostring(self):
        ugly = ET.tostring(self.element, encoding='unicode')
        dom = minidom.parseString(ugly)
        pretty = dom.toprettyxml()
        pretty = pretty.splitlines()
        pretty[0] = '<!DOCTYPE RCC>'
        pretty[1] = '<RCC version="1.0">'
        return '\n'.join(pretty)

    def write(self, filename: Path):
        assert self.parent is None
        # ugly = ET.tostring(self.element, encoding='unicode')
        # dom = minidom.parseString(ugly)
        # pretty = dom.toprettyxml()
        # pretty = pretty.splitlines()
        # pretty[0] = '<!DOCTYPE RCC>'
        # pretty[1] = '<RCC version="1.0">'
        # filename.write_text('\n'.join(pretty))
        filename.write_text(self.tostring())

    @classmethod
    def create(cls, **kwargs):
        element = kwargs.get('element')
        if element is not None:
            tag = element.tag
        else:
            tag = kwargs.get('tag', cls.TAG)
        _cls = cls.cls_for_tag(tag)
        return _cls(**kwargs)

    @classmethod
    def cls_for_tag(cls, tag: str):
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
    def tag(self): return self.element.tag

    @property
    def attrib(self): return self.element.attrib

    @property
    def text(self):
        return self.element.text
    @text.setter
    def text(self, value):
        self.element.text = value

    def add_child(self, **kwargs):
        kwargs['parent'] = self
        child = self.create(**kwargs)
        self.children.append(child)
        return child

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'
    def __str__(self):
        return self.tag

class QRCDocument(QRCElement):
    TAG = 'RCC'

    @classmethod
    def from_file(cls, filename: Path):
        root = ET.fromstring(filename.read_text())
        return cls(element=root)

    def search_for_file(self, filename: Path):
        for c in self.children:
            if not isinstance(c, QRCResource):
                continue
            r = c.search_for_file(filename)
            if r is not None:
                return r


class QRCResource(QRCElement):
    TAG = 'qresource'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'prefix' in kwargs:
            self.prefix = kwargs['prefix']

    @property
    def prefix(self):
        return self.attrib.get('prefix')
    @prefix.setter
    def prefix(self, value: str):
        self.attrib['prefix'] = value

    def search_for_file(self, filename: Path):
        if self.prefix:
            filename = Path(self.prefix) / filename
        for c in self.children:
            if not isinstance(c, QRCFile):
                continue
            if filename == c.filename:
                return c

class QRCFile(QRCElement):
    TAG = 'file'
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for attr in ['filename', 'alias']:
            if attr in kwargs:
                setattr(self, attr, kwargs[attr])

    @property
    def filename(self):
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
    def alias(self):
        return self.attrib.get('alias')
    @alias.setter
    def alias(self, value):
        if isinstance(value, Path):
            value = str(value)
        self.attrib['alias'] = value
