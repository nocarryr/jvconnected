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

logger = logging.getLogger(__name__)


DocumenterIsAttr = tp.NewType('DocumenterIsAttr', tp.Tuple[Documenter, bool])
CategorizedDocumenters = tp.NewType('CategorizedDocumenters', tp.List[tp.Tuple[str, DocumenterIsAttr]])

SECTIONS = {
    'class':[
        ('Attributes', ['property', 'attribute']),
        ('Methods', ['method']),
    ],
}


def int_option(arg: tp.Any) -> int|None:
    if arg in (None, True):
        return None
    elif isinstance(arg, str):
        return int(arg)
    else:
        raise ValueError(f'invalid value for int option: {arg}')


def get_role_for_directive(env, directive: str, domain: str='py') -> str:
    objtypes = env.domains[domain].object_types
    if directive not in objtypes:
        raise KeyError(f'{directive} not found in {objtypes}')
    objtype = objtypes[directive]
    return objtype.roles[0]


class BlockItem:
    """Container for items in :class:`IndentBlock`
    """
    item: str|'IndentBlock'
    """The item itself.  Either a string or a :class:`IndentBlock` instance
    """
    sourcename: str|None
    lineno: tp.Tuple[int]
    use_indent: bool
    """If ``False``, no indentation will be used for the :attr:`item`.
    (default is ``True``)
    """
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
    """Nestable list container for text items to assist in building up blocks
    of indented text

    When an :class:`IndentBlock` instance is added as a child, its
    :attr:`indent <num_indent>` is increased by one level.

    Arguments:
        initlist: A list of items to add on initialization
        sourcename:
        parent: The parent :class:`IndentBlock` (or ``None`` if this is the root)

    Keyword Arguments:
        use_indent (bool): The value for :attr:`BlockItem.use_indent`.
            Default is ``False``
    """

    content: tp.List[BlockItem]
    """The content for this block as a list of :class:`BlockItem`
    """

    indent_increment: tp.ClassVar[int] = 3
    """Amount of spaces to use for each level of indentation
    """

    block_item_parent: BlockItem
    """The :class:`BlockItem` containing this block (created automatically)
    """

    __slots__ = (
        'content', '_parent', '_num_parents',
        '_root_sourcename', 'block_item_parent',
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
        self.block_item_parent = block_item
        if parent is None:
            assert sourcename is not None, 'Root must have sourcename set'
        if initlist is not None:
            self.extend(initlist)

    @property
    def parent(self) -> 'IndentBlock'|None:
        """The parent :class:`IndentBlock`, or None if this is the root block
        """
        return self._parent
    @parent.setter
    def parent(self, value: 'IndentBlock'|None):
        if value is self.parent:
            return
        if self.parent is not None:
            self.parent.content.remove(self.block_item_parent)
        self._num_parents = None
        self._root_sourcename = None
        self._parent = value

    @property
    def sourcename(self) -> str:
        return self.block_item_parent.sourcename
    @sourcename.setter
    def sourcename(self, value: str):
        if value == self.sourcename:
            return
        self.block_item_parent.sourcename = value
        self._root_sourcename = None

    @property
    def root_sourcename(self) -> str:
        sourcename = getattr(self, '_root_sourcename', None) or self.sourcename
        if sourcename is None:
            sourcename = self._root_sourcename = self.parent.root_sourcename
        return sourcename

    @property
    def num_parents(self) -> int:
        """Number of parents for the block, or the nest level
        """
        n = getattr(self, '_num_parents', None)
        if n is None:
            if self.parent is None:
                n = self._num_parents = 0
            else:
                n = self._num_parents = self.parent.num_parents + 1
        return n

    @property
    def num_indent(self) -> int:
        """Number of indent spaces

        :attr:`num_parents` X :attr:`indent_increment`
        """
        if not self.block_item_parent.use_indent:
            return 0
        return self.num_parents * self.indent_increment

    def append(self,
        item: str|'IndentBlock'|tp.List[str],
        sourcename: str|None = None,
        *lineno: int, **kwargs
    ) -> str|'IndentBlock':
        """Append either a line of text or a child :class:`IndentBlock`

        If *item* is a list, an :class:`IndentBlock` will be created and added
        as a child.

        Keyword Arguments:
            use_indent (bool): The value for :attr:`BlockItem.use_indent`.
                Default is ``False``
        """
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

    def extend(self, items: tp.Sequence[str|'IndentBlock'|tp.List[str]]) -> None:
        """Effectively calls :meth:`append` for each item in *items*
        """
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
        item: tp.List[str]|'IndentBlock'|None = None,
        sourcename: str|None = None,
        *lineno: int, **kwargs
    ) -> 'IndentBlock':
        """Add an :class:`IndentBlock` child

        If *item* is an :class:`IndentBlock` instance, it will be added as a
        child. Otherwise, an instance will be created and *item* will be passed
        as the *initlist* argument.

        Keyword Arguments:
            use_indent (bool): The value for :attr:`BlockItem.use_indent`.
                Default is ``False``
        """
        use_indent = kwargs.get('use_indent', True)
        if isinstance(item, IndentBlock):
            blk = item
            item = blk.block_item_parent
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
            blk.block_item_parent.lineno = tuple(lineno)
            blk.block_item_parent.use_indent = use_indent
        item = blk.block_item_parent
        return item

    def __iter__(self) -> tp.Iterator[BlockItem]:
        yield from self.content

    def walk(self) -> tp.Iterator[BlockItem]:
        """Walk through every :class:`BlockItem` in this instance and its children
        """
        yield self.block_item_parent
        for item in self.content:
            if isinstance(item.item, IndentBlock):
                yield from item.walk()
            else:
                yield item

    def walk_blocks(self) -> tp.Iterator['IndentBlock']:
        """Walk through every :class:`IndentBlock` contained in this instance and
        its children
        """
        yield self
        for item in self.content:
            if isinstance(item.item, IndentBlock):
                yield from item.item.walk_blocks()

    def get_indented(self, initial_indent: int = 0) -> tp.Iterator[str, str, tp.Tuple[int]]:
        """Get indented text lines for this instance and all of its children

        Arguments:
            initial_indent: Additional number of indentation spaces to use
                for each line
        """
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
        """Add the contents from :meth:`get_indented` to the given StringList
        """
        for line, sourcename, lineno in self.get_indented(initial_indent):
            sl.append(line, sourcename, *lineno)

    def add_to_documenter(self, documenter: Documenter, initial_indent: int = 0) -> None:
        """Add the contents from :meth:`get_indented` to the given :class:`Documenter`

        The documenter's indent is added to the *initial_indent*
        """
        indent = len(documenter.indent) + initial_indent
        self.add_to_stringlist(documenter.directive.result, indent)



class InterruptingMemberDocumenter:
    """Mixin to intercept member collection and member document generation
    """
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
        """Called after :meth:`sort_members` and before :meth:`_do_document_members`

        *memberdocumenters* must be returned, but can be modified if needed
        """
        return memberdocumenters

    def _do_document_members(
        self,
        memberdocumenters: tp.List[DocumenterIsAttr],
        members_check_module: bool
    ) -> None:
        """Call :meth:`_document_single_member` for each item in *memberdocumenters*
        """
        for documenter, isattr in memberdocumenters:
            self._document_single_member(documenter, isattr, members_check_module)

    def _document_single_member(
        self, documenter: Documenter, isattr: bool, members_check_module: bool,
    ) -> None:
        """Document a single member
        """
        documenter.generate(
            all_members=True, real_modname=self.real_modname,
            check_module=members_check_module and not isattr
        )


class SectionedModuleDocumenter(InterruptingMemberDocumenter, _ModuleDocumenter):
    """ModuleDocumenter that adds section headings for each member
    """
    option_spec = dict(_ModuleDocumenter.option_spec)
    option_spec['section-level'] = int_option
    priority = _ModuleDocumenter.priority + 1
    objtype = 'sectionedmodule'
    directivetype = 'module'
    _section_levels = ['=', '-', '^', '"']

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
        objrole = get_role_for_directive(self.env, objtype)

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
    """A ClassDocumenter that organizes its members into named categories with
    summary lists
    """
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

    def categorize_documenters(
        self, memberdocumenters: tp.List[DocumenterIsAttr]
    ) -> tp.Tuple[CategorizedDocumenters, int]:
        results: tp.List[tp.Tuple[str, tp.List[DocumenterIsAttr]]] = []
        sections = self.config.autodoc_sections_map['class']
        max_section = 0
        tmp = {}
        remaining = memberdocumenters.copy()
        for documenter, isattr in memberdocumenters.copy():
            for section_name, objtypes in sections:
                if documenter.objtype not in objtypes:
                    directivetype = getattr(documenter, 'directivetype', None)
                    if directivetype is not None and directivetype not in objtypes:
                        continue
                section = tmp.setdefault(section_name, [])
                section.append((documenter, isattr))
                remaining.remove((documenter, isattr))
                break
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
                role_name = get_role_for_directive(self.env, directive)
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

            root = IndentBlock([
                f'.. card::',
                ''
            ], sourcename)
            card_content = root.append([
                f'.. dropdown:: {section_name.title()}',
            ])
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


def setup(app: Sphinx) -> tp.Dict[str, tp.Any]:
    app.setup_extension('sphinx.ext.autodoc')
    app.add_config_value(
        'autodoc_sections_map', default=SECTIONS,
        rebuild='env', types=[dict],
    )
    app.add_autodocumenter(SectionedModuleDocumenter)
    app.add_autodocumenter(CategorizedClassDocumenter)

    return {'version': '0.1', 'parallel_read_safe': True}
