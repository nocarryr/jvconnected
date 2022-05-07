from __future__ import annotations
import typing as tp
from pathlib import Path
import json
import itertools

from docutils.statemachine import ViewList, StringList
from docutils.parsers.rst.states import Struct
from sphinx.application import Sphinx
from sphinx.ext.autodoc import (
    Documenter,
    ClassDocumenter as _ClassDocumenter,
    ModuleDocumenter as _ModuleDocumenter,
    ALL,
)
from sphinx.ext.autodoc.directive import DocumenterBridge, Options
from sphinx.util import logging

from docutils import nodes
from docutils.nodes import Node
from docutils.parsers.rst import directives
from sphinx import addnodes
from sphinx.util.docutils import SphinxDirective
from sphinx.util.typing import OptionSpec
from sphinx.util.nodes import nested_parse_with_titles
# from sphinx.domains import ObjType
# from sphinx.domains.python import (
#     PyXRefRole, PyAttribute, PyMethod, PyObject, type_to_xref, _parse_arglist,
# )

logger = logging.getLogger(__name__)

DEBUG_DATA_DIR = Path('.') / 'autodoc_debug'
DEBUG_DATA_DIR.mkdir(exist_ok=True)

DocumenterIsAttr = tp.NewType('DocumenterIsAttr', tp.Tuple[Documenter, bool])
CategorizedDocumenters = tp.NewType('CategorizedDocumenters', tp.List[tp.Tuple[str, DocumenterIsAttr]])

SECTIONS = {
    'class':[
        ('Properties', ['dispatcherproperty', 'qtproperty']),
        ('Events', ['event', 'eventmethod', 'qtsignal']),
        ('Attributes', ['property', 'attribute']),
        ('Slots', ['qtslot']),
        ('Methods', ['method']),
    ],
}

DIRECTIVE_ROLE_MAP = {
    'method':'meth',
    'property':'attr',
    'attribute':'attr',
    'event':'event',
    'dispatcherproperty':'dispatcherproperty',
    'qtsignal':'qtsignal',
    'qtslot':'qtslot',
    'qtproperty':'qtproperty',
}


def int_option(arg: tp.Any) -> int|None:
    if arg in (None, True):
        return None
    elif isinstance(arg, str):
        return int(arg)
    else:
        raise ValueError(f'invalid value for int option: {arg}')


class BlockItem:
    item: str|'IndentBlock'
    sourcename: str|None
    lineno: tp.Tuple[int]
    use_indent: bool
    __slots__ = ('item', 'sourcename', 'lineno', 'use_indent')
    def __init__(
        self, item: str|'IndentBlock',
        sourcename: str|None = None,
        use_indent: bool = True,
        *lineno: int,
    ):
        self.item = item
        self.sourcename = sourcename
        self.lineno = tuple(lineno)
        self.use_indent = use_indent

    def __repr__(self):
        return f'<{self.__class__.__name__}: "{self}">'

    def __str__(self):
        return str(self.item)


class IndentBlock:
    content: tp.List[BlockItem]
    indent_increment: tp.ClassVar[int] = 3

    __slots__ = (
        'content', '_parent', '_num_parents',
        '_root_sourcename', '_block_item_parent',
    )
    def __init__(
        self,
        initlist: tp.List[str]|None = None,
        sourcename: str|None = None,
        parent: 'IndentBlock'|None = None,
        block_item: BlockItem|None = None,
        *lineno: int, **kwargs
    ):
        use_indent = kwargs.get('use_indent', True)
        self.content = []
        self._parent = parent
        if block_item is None:
            block_item = BlockItem(
                item=self, sourcename=sourcename, use_indent=use_indent, *lineno,
            )
        else:
            block_item.item = self
            block_item.sourcename = sourcename
            block_item.lineno = tuple(lineno)
            block_item.use_indent = use_indent
        self._block_item_parent = block_item
        if parent is None:
            assert sourcename is not None, 'Root must have sourcename set'
        if initlist is not None:
            self.extend(initlist)

    @property
    def parent(self) -> 'IndentBlock'|None:
        return self._parent
    @parent.setter
    def parent(self, value: 'IndentBlock'|None):
        if value is self.parent:
            return
        if self.parent is not None:
            self.parent.content.remove(self._block_item_parent)
        self._num_parents = None
        self._root_sourcename = None
        self._parent = value

    @property
    def sourcename(self) -> str:
        return self._block_item_parent.sourcename
    @sourcename.setter
    def sourcename(self, value: str):
        if value == self.sourcename:
            return
        self._block_item_parent.sourcename = value
        self._root_sourcename = None

    @property
    def root_sourcename(self) -> str:
        sourcename = getattr(self, '_root_sourcename', None) or self.sourcename
        if sourcename is None:
            sourcename = self._root_sourcename = self.parent.root_sourcename
        return sourcename

    @property
    def num_parents(self) -> int:
        n = getattr(self, '_num_parents', None)
        if n is None:
            if self.parent is None:
                n = self._num_parents = 0
            else:
                n = self._num_parents = self.parent.num_parents + 1
        return n

    @property
    def num_indent(self) -> int:
        if not self._block_item_parent.use_indent:
            return 0
        return self.num_parents * self.indent_increment

    def append(self,
        item: str|'IndentBlock'|tp.List[str],
        sourcename: str|None = None,
        *lineno: int, **kwargs
    ) -> str|'IndentBlock':
        use_indent = kwargs.get('use_indent', True)
        if isinstance(item, (IndentBlock, list)):
            item = self._create_child(item, sourcename, *lineno, **kwargs)
            item.item.parent = self
        elif isinstance(item, str):
            item = BlockItem(item, sourcename, use_indent, *lineno)
        else:
            raise ValueError(f'invalid item type: {item!r}')
        self.content.append(item)
        return item.item

    def extend(self, items):
        for item in items:
            self.append(item)

    # def _content_len(self) -> int:
    #     return len((item for item in self if isinstance(item.item, str)))

    def __len__(self):
        # return sum((blk._content_len() for blk in self.walk_blocks()))
        def keyfunc(item):
            if isinstance(item.item, str):
                return 'str'
            else:
                return 'blk'
        v = 0
        for key, g in itertools.groupby(self.content, keyfunc):
            if key == 'str':
                v += len([item for item in g])
            else:
                v += sum((len(item.item) for item in g))
        return v

    def add_child(self,
        item: str|'IndentBlock'|None = None,
        sourcename: str|None = None,
        *lineno: int, **kwargs
    ) -> 'IndentBlock':
        use_indent = kwargs.get('use_indent', True)
        if isinstance(item, IndentBlock):
            blk = item
            item = blk._block_item_parent
            blk.parent = self
        item = self._create_child(item, sourcename, *lineno, **kwargs)
        self.content.append(item)
        return item.item

    def _create_child(self,
        item: str|'IndentBlock'|None = None,
        sourcename: str|None = None,
        *lineno: int, **kwargs
    ) -> BlockItem:
        use_indent = kwargs.get('use_indent', True)
        if not isinstance(item, IndentBlock):
            blk = IndentBlock(
                item, sourcename=sourcename, parent=self, *lineno, **kwargs
            )
        else:
            blk = item
            blk._block_item_parent.lineno = tuple(lineno)
            blk._block_item_parent.use_indent = use_indent
        item = blk._block_item_parent
        return item

    def __iter__(self) -> tp.Iterator[BlockItem]:
        yield from self.content

    def walk(self) -> tp.Iterator[BlockItem]:
        yield self._block_item_parent
        for item in self.content:
            if isinstance(item.item, IndentBlock):
                yield from item.walk()
            else:
                yield item

    def walk_blocks(self) -> tp.Iterator['IndentBlock']:
        yield self
        for item in self.content:
            if isinstance(item.item, IndentBlock):
                yield from item.item.walk_blocks()

    def get_indented(self, initial_indent: int = 0) -> tp.Iterator[str, str, tp.Tuple[int]]:
        num_indent = self.num_indent + initial_indent
        indent = ' '*num_indent
        default_sourcename = self.root_sourcename
        for item in self:
            if isinstance(item.item, IndentBlock):
                yield from item.item.get_indented(initial_indent)
            else:
                line = item.item
                if len(line.strip()):
                    if item.use_indent:
                        line = f'{indent}{line}'
                else:
                    line = ''
                sourcename = item.sourcename
                if sourcename is None:
                    sourcename = default_sourcename
                yield line, sourcename, item.lineno

    def add_to_stringlist(self, sl: StringList, initial_indent: int = 0) -> None:
        for line, sourcename, lineno in self.get_indented(initial_indent):
            sl.append(line, sourcename, *lineno)

    def add_to_documenter(self, documenter: Documenter, initial_indent: int = 0) -> None:
        indent = len(documenter.indent) + initial_indent
        self.add_to_stringlist(documenter.directive.result, indent)



# def serialize_stringlist(sl: StringList) -> tp.Dict[str, tp.Any]:
#     d = dict(
#         data=sl.data,
#         items=sl.items,
#         parent_offset=sl.parent_offset,
#         parent=None,
#     )
#     if sl.parent is not None:
#         d['parent'] = serialize_stringlist(sl.parent)
#     return d
#
# def deserialize_stringlist(data: tp.Dict[str, tp.Any]) -> StringList:
#
#     def _deserialize(_data):
#         p = d['parent']
#         if p is not None:
#             p = _deserialize(p)
#         sl = StringList(
#             initlist=d['data'], items=d['items'], parent=p,
#             parent_offset=d['parent_offset'],
#         )
#         assert sl.data == d['data']
#         assert sl.items == d['items']
#         return sl
#
#     return _deserialize(data)
#
#
# def serialize_doc_bridge(br: DocumenterBridge) -> tp.Dict[str, tp.Any]:
#     d = dict(
#         lineno=br.lineno,
#         record_dependencies=list(br.record_dependencies),
#         result=serialize_stringlist(br.result),
#     )
#     return d
#
# def deserialize_doc_bridge(data: tp.Dict[str, tp.Any]) -> DocumenterBridge:
#     result = data.pop('result')
#     record_dependencies = set(data.pop('record_dependencies'))
#     br = DocumenterBridge(**data)
#     br.result = deserialize_stringlist(result)
#     br.record_dependencies = record_dependencies
#     return br


class InterruptingMemberDocumenter:
    # Direct copy-paste from Documenter.document_members:
    # https://github.com/sphinx-doc/sphinx/blob/e7cba3516e6e3cd1cf90c29068c63c011e860204/sphinx/ext/autodoc/__init__.py#L820-L863
    #
    # Override so we can intercept between `self.sort_members` and
    # `documenter.generate`
    def document_members(self, all_members: bool = False) -> None:
        if self.doc_as_attr:
            return
        """Generate reST for member documentation.
        If *all_members* is True, document all members, else those given by
        *self.options.members*.
        """
        # set current namespace for finding members
        self.env.temp_data['autodoc:module'] = self.modname
        if self.objpath:
            self.env.temp_data['autodoc:class'] = self.objpath[0]

        want_all = (all_members or
                    self.options.inherited_members or
                    self.options.members is ALL)
        # find out which members are documentable
        members_check_module, members = self.get_object_members(want_all)

        # document non-skipped members
        memberdocumenters: List[Tuple[Documenter, bool]] = []
        for (mname, member, isattr) in self.filter_members(members, want_all):
            classes = [cls for cls in self.documenters.values()
                       if cls.can_document_member(member, mname, isattr, self)]
            if not classes:
                # don't know how to document this member
                continue
            # prefer the documenter with the highest priority
            classes.sort(key=lambda cls: cls.priority)
            # give explicitly separated module name, so that members
            # of inner classes can be documented
            full_mname = self.modname + '::' + '.'.join(self.objpath + [mname])
            documenter = classes[-1](self.directive, full_mname, self.indent)
            memberdocumenters.append((documenter, isattr))

        member_order = self.options.member_order or self.config.autodoc_member_order
        memberdocumenters = self.sort_members(memberdocumenters, member_order)

        # <----------- Override here
        memberdocumenters = self._before_document_members(
            memberdocumenters, members_check_module,
        )
        self._do_document_members(memberdocumenters, members_check_module)
        # ------------------->

        # reset current objects
        self.env.temp_data['autodoc:module'] = None
        self.env.temp_data['autodoc:class'] = None

    def _before_document_members(
        self,
        memberdocumenters: tp.List[DocumenterIsAttr],
        members_check_module: bool,
    ) -> tp.List[DocumenterIsAttr]:
        return memberdocumenters

    def _do_document_members(
        self,
        memberdocumenters: tp.List[DocumenterIsAttr],
        members_check_module: bool
    ) -> None:
        for documenter, isattr in memberdocumenters:
            self._document_single_member(documenter, isattr, members_check_module)

    def _document_single_member(
        self, documenter: Documenter, isattr: bool, members_check_module: bool,
    ) -> None:
        documenter.generate(
            all_members=True, real_modname=self.real_modname,
            check_module=members_check_module and not isattr
        )


class SectionedModuleDocumenter(InterruptingMemberDocumenter, _ModuleDocumenter):
    option_spec = dict(_ModuleDocumenter.option_spec)
    option_spec['section-level'] = int_option
    priority = _ModuleDocumenter.priority + 1
    objtype = 'sectionedmodule'
    directivetype = 'module'
    _section_levels = ['=', '-', '^', '"']
    _objtypes = {
        'class':'class', 'attribute':'attr', 'function':'func', 'data':'data',
    }

    def import_object(self, raiseerror: bool = False) -> bool:
        ret = super().import_object(raiseerror)
        if not hasattr(self, 'doc_as_attr'):
            self.doc_as_attr = False
        return ret

    def _document_single_member(
        self, documenter: Documenter, isattr: bool, members_check_module: bool,
    ) -> None:
        section_level = self.options.get('section-level', 2)
        section_char = self._section_levels[section_level-1]
        objtype = getattr(documenter, 'directivetype', documenter.objtype)
        if objtype in self._objtypes:
            objrole = self._objtypes[objtype]
            if (documenter.parse_name() and
                documenter.import_object() and
                documenter.check_module()
            ):
                objname = documenter.object_name
                sourcename = documenter.get_sourcename()
                obj_ref = f':py:{objrole}:`{objname} <{documenter.fullname}>`'
                section_str = section_char * len(obj_ref)

                hdr_txt = [
                    '',
                    section_str,
                    obj_ref,
                    section_str,
                    '',
                ]
                for line in hdr_txt:
                    self.directive.result.append(line, sourcename)
                members_check_module = False
        super()._document_single_member(documenter, isattr, members_check_module)


class CategorizedClassDocumenter(InterruptingMemberDocumenter, _ClassDocumenter):
    option_spec = dict(_ClassDocumenter.option_spec)
    priority = _ClassDocumenter.priority + 1
    objtype = 'categorizedclass'
    directivetype = 'class'

    # def patch_directive(self):
    #     sourcename = self.get_sourcename()
    #     directive = self.directive
    #     if not isinstance(directive.result, IndentBlock):
    #         directive._orig_result = directive.result
    #         directive.result = IndentBlock(sourcename=sourcename)
    # def unpatch_directive(self):
    #     sourcename = self.get_sourcename()
    #     directive = self.directive
    #     if not isinstance(directive.result, IndentBlock):
    #         return
    #     blk = directive.result
    #     if blk.sourcename != sourcename:
    #         return
    #     sl = directive._orig_result
    #     blk.add_to_stringlist(sl, len(self.indent))
    #     directive.result = sl
    #     directive.indent_block = blk
    #
    # def __init__(self, directive: DocumenterBridge, name: str, indent: str = ''):
    #     if not isinstance(directive.result, IndentBlock):
    #         directive._orig_result = directive.result
    #         directive.result = IndentBlock(sourcename='')
    #     super().__init__(directive, name, indent)

    def _before_document_members(
        self,
        memberdocumenters: tp.List[DocumenterIsAttr],
        members_check_module: bool,
    ) -> tp.List[DocumenterIsAttr]:
        categorized, max_section = self.categorize_documenters(memberdocumenters)
        use_summary = max_section >= 5 and len(categorized) > 1
        if use_summary:
            self.add_section_summary(categorized, max_section)
        if len(categorized) > 1:
            self.document_categorized_members(
                categorized, members_check_module, dropdown_open=not use_summary,
            )
            return []
        else:
            return memberdocumenters

    # def generate(
    #     self, more_content: StringList|None = None, real_modname: str|None = None,
    #     check_module: bool = False, all_members: bool = False
    # ) -> None:
    #     super().generate(more_content, real_modname, check_module, all_members)
    #     if self.fullname in ['jvconnected.engine.Engine', 'jvconnected.device.Device']:
    #         ser = serialize_doc_bridge(self.directive)
    #         fn = DEBUG_DATA_DIR / f'{self.fullname}.json'
    #         fn.write_text(json.dumps(ser, indent=2))
    #         fn = DEBUG_DATA_DIR / f'{self.fullname}.rst'
    #         fn.write_text('\n'.join(ser['result']['data']))

    def categorize_documenters(
        self, memberdocumenters: tp.List[DocumenterIsAttr]
    ) -> tp.Tuple[CategorizedDocumenters, int]:
        results: tp.List[tp.Tuple[str, tp.List[DocumenterIsAttr]]] = []
        sections = SECTIONS['class']
        max_section = 0
        tmp = {}
        remaining = memberdocumenters.copy()
        for documenter, isattr in memberdocumenters.copy():
            for section_name, objtypes in sections:
                if documenter.objtype not in objtypes:
                    continue
                section = tmp.setdefault(section_name, [])
                section.append((documenter, isattr))
                remaining.remove((documenter, isattr))
        for section_name, _unused in sections:
            if section_name in tmp:
                results.append((section_name, list(tmp[section_name])))
        if len(tmp):
            max_section = max([len(l) for l in tmp.values()])
        else:
            max_section = 0
        max_section = max([max_section, len(remaining)])
        if len(remaining):
            results.append((None, remaining))
        return results, max_section

    def _get_section_ref(self, section_name: str) -> str:
        objname = '-'.join(self.fullname.split('.'))
        return '-'.join([objname, section_name])

    def add_line_unindented(self, line: str, source: str, *lineno: int) -> None:
        if line.strip():
            self.directive.result.append(line, source, *lineno)
        else:
            self.directive.result.append('', source, *lineno)

    def add_section_summary(self, categorized: CategorizedDocumenters, max_section: int) -> None:
        sourcename = self.get_sourcename()

        root = dropdown = IndentBlock([
            '.. dropdown:: Summary',
            '   :open:',
            '',
        ], sourcename)
        grid_root = dropdown.append([
            '.. grid:: 1 1 2 2',
            # '   :padding: 0',
            '',
        ])
        grid = grid_root.add_child()

        for section_name, t in categorized:
            if section_name is None:
                section_name = 'Other'
            if not len(t):
                continue
            sec_ref = self._get_section_ref(section_name)
            sec_xref = f':ref:`{section_name.title()} <{sec_ref}>`'

            grid.extend([
                '.. grid-item-card::',
                '',
            ])

            section_content = grid.append([
                sec_xref,
                '^^^',
            ])

            for documenter, isattr in t:
                if not documenter.parse_name():
                    continue
                lbl_text = documenter.objpath[-1]
                directive = getattr(documenter, 'directivetype', documenter.objtype)
                role_name = DIRECTIVE_ROLE_MAP[directive]
                xref = f':py:{role_name}:`{lbl_text} <{documenter.fullname}>`'
                section_content.append(f'* {xref}')

            grid.append('')

        root.append('')
        root.add_to_documenter(self)

    def document_categorized_members(
        self, categorized: CategorizedDocumenters, members_check_module: bool,
        dropdown_open: bool = True
    ) -> None:
        sourcename = self.get_sourcename()

        for section_name, t in categorized:
            if section_name is None:
                section_name = 'Other'
            if not len(t):
                continue
            sec_ref = self._get_section_ref(section_name)

            # # root = IndentBlock([], sourcename)
            # #
            # # dropdown = root.append([#IndentBlock([
            # #     f'.. dropdown:: {section_name.title()}',
            # # ])
            # root = dropdown = IndentBlock([], sourcename)
            #
            # root.append(#IndentBlock([
            #     f'.. dropdown:: {section_name.title()}',
            # )
            #
            # if dropdown_open:
            #     dropdown.append('   :open:')
            # dropdown.append('')
            # card = dropdown.append([#IndentBlock([
            #     f'.. _{sec_ref}:',
            #     '',
            #     f'.. card::',
            #     '',
            # ])

            # card_content = card.add_child()
            root = IndentBlock([
                f'.. card::',
                ''
            ], sourcename)
            card_content = root.append([
                f'.. dropdown:: {section_name.title()}',
            ])
            # card = root.add_child()
            # card.append('.. dropdown::')
            if dropdown_open:
                card_content.append('   :open:')
            card_content.append('')
            dropdown_content = card_content.add_child()
            dropdown_content.append(f'.. _{sec_ref}:')



            root.add_to_documenter(self)

            for documenter, isattr in t:
                num_indent = dropdown_content.num_indent + len(self.indent)
                indent = ' '*num_indent
                documenter.indent = indent
                self._document_single_member(documenter, isattr, members_check_module)

            self.add_line('', sourcename)


# class SectionDirective(SphinxDirective):
#     has_content = True
#     required_arguments = 0
#     optional_arguments = 0
#     final_argument_whitespace = False
#     option_spec = {
#         'title':directives.unchanged_required,
#         # 'ref-domain':directives.unchanged,
#         # 'ref-role':directives.unchanged,
#         'ref-target':directives.unchanged_required,
#     }
#
#     def run(self) -> tp.List[Node]:
#         # nodes = []
#         # self.options.setdefault('ref-domain', 'py')
#         # keys = ['ref-domain', 'ref-role', 'ref-target']
#         # ref_vars = [self.options.get(key) for key in keys]
#         # if None not in ref_vars:
#         #     domain, role, target = ref_vars
#         #     # ref = f':{domain}:{role}:`{target}`'
#         #     nodes.append(
#         #         # pending_xref('', )
#         #         type_to_xref(target, self.env, suppress_prefix=True),
#         #     )
#         sect = nodes.section(ids=[self.options['ref-target']])
#         title = nodes.title()
#         title += nodes.Text(self.options['title'])
#         sect += title
#         # sect += nodes.title(self.options.get('title'))
#         nested_parse_with_titles(self.state, self.content, sect)
#         return [sect]


def setup(app: Sphinx) -> tp.Dict[str, tp.Any]:
    app.setup_extension('sphinx.ext.autodoc')
    app.add_autodocumenter(SectionedModuleDocumenter)
    app.add_autodocumenter(CategorizedClassDocumenter)

    # app.setup_extension('sphinx.directives')
    # app.add_directive_to_domain('py', 'mysection', SectionDirective)

    return {'version': '0.1', 'parallel_read_safe': True}
