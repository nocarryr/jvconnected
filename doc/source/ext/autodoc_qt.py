from __future__ import annotations
import typing as tp
import ast

from docutils.statemachine import StringList
import sphinx
from sphinx.application import Sphinx
from sphinx.locale import _, __
from sphinx.util import logging
from sphinx.util import inspect
from sphinx.util.typing import (
    get_type_hints, stringify as stringify_typehint, OptionSpec,
)
from sphinx.util.inspect import safe_getattr
from sphinx.pycode import ModuleAnalyzer

from sphinx.ext.autodoc import (
    ModuleDocumenter, MethodDocumenter, AttributeDocumenter, EMPTY,
)

from sphinx import addnodes
from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.domains import ObjType
from sphinx.domains.python import (
    PyXRefRole, PyAttribute, PyMethod, _parse_arglist,
)

from PySide2.QtCore import Property, Signal, Slot

from jvconnected.ui.utils import AnnotatedQtSignal

logger = logging.getLogger(__name__)


PYSIDE_VER = 'PySide6'

FULL_NAMES = {
    cls: '.'.join([cls.__module__, cls.__module__, cls. __qualname__])
    for cls in [Property, Signal, Slot]
}

QT_REFS = {
    'Signal':{
        'reftarget':f'{PYSIDE_VER}.QtCore.{PYSIDE_VER}.QtCore.Signal',
        'reftype':'class',
        'refdomain':'py',
    },
    'Slot':{
        'reftarget':f'{PYSIDE_VER}.QtCore.{PYSIDE_VER}.QtCore.Slot',
        'reftype':'class',
        'refdomain':'py',
    },
    'Property':{
        'reftarget':f'{PYSIDE_VER}/QtCore/Property',
        'reftype':'doc',
        'refdomain':'std',
    }
}



def qt_type_to_xref(
    target: str, env: 'BuildEnvironment' = None,
    suppress_prefix: bool = False, domain: str = 'py',
) -> addnodes.pending_xref:
    kwargs = {}

    objname = target.split('.')[-1]
    refspec = QT_REFS[objname]
    kwargs = refspec.copy()

    if suppress_prefix:
        title = target.split('.')[-1]
    else:
        title = target

    contnodes = [nodes.Text(title)]
    xref = addnodes.pending_xref('', *contnodes, **kwargs)
    xref['intersphinx'] = True
    xref['inventory'] = PYSIDE_VER
    return xref



class SlotDecoratorFinder:
    """Parses module ast trees to find ``@Slot`` or ``@asyncSlot`` methods

    Results are cached per module
    """
    def __init__(self):
        self.cache = {}
    def parse_module(self, modname: str):
        if modname in self.cache:
            return self.cache[modname]
        logger.debug(f'Parsing "{modname}"')
        result = self.cache[modname] = {}
        analyzer = ModuleAnalyzer.for_module(modname)
        analyzer.analyze()
        tree = ast.parse(analyzer.code)
        for fullname, decorator_name in self.iter_find_slot_defs(tree):
            result[fullname] = decorator_name
        return result

    def iter_find_slot_defs(
        self, node: ast.AST, parent: ast.AST|None = None
    ) -> tp.Iterable[tp.Tuple[str, str]]:
        if isinstance(node, (ast.Module, ast.ClassDef)):
            for _node in node.body:
                yield from self.iter_find_slot_defs(_node, node)
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
              isinstance(parent, ast.ClassDef)):

            fullname = '.'.join([parent.name, node.name])

            if hasattr(node, 'decorator_list'):
                for dec in node.decorator_list:
                    if not isinstance(dec, ast.Call):
                        continue
                    func = dec.func

                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    else:
                        name = None
                    if name is None:
                        continue
                    if name.split('.')[-1] in ['Slot', 'asyncSlot']:
                        yield fullname, name

slot_finder: SlotDecoratorFinder = SlotDecoratorFinder()
"""Global :class:`SlotDecoratorFinder` instance"""

def list_option(arg: tp.Any) -> object|tp.List[str]:
    if arg in (None, True):
        return EMPTY
    elif arg is False:
        return None
    return [x.strip() for x in arg.split(',') if x.strip]


class QtSignalDocumenter(MethodDocumenter):
    """Documenter for QtCore.Signal methods
    """
    objtype = 'qtsignal'
    directivetype = 'qtsignal'
    priority = AttributeDocumenter.priority + 1
    option_spec = dict(MethodDocumenter.option_spec)
    option_spec['argtypes'] = list_option
    option_spec['argnames'] = list_option
    _anno_qualname: tp.ClassVar[str] = AnnotatedQtSignal.__qualname__

    @classmethod
    def can_document_member(
        cls, member: tp.Any, membername: str, isattr: bool, parent: tp.Any
    ) -> bool:
        if not isinstance(parent, ModuleDocumenter):
            if isinstance(member, Signal):
                return True
        return False

    def get_signal_anno(self):
        annotations = safe_getattr(self.parent, '__annotations__', {})

        obj_anno = annotations.get(self.objpath[-1])
        if obj_anno is None:
            return
        if safe_getattr(obj_anno, '__qualname__', '') != self._anno_qualname:
            return
        sig_anno = get_type_hints(obj_anno, None, self.config.autodoc_type_aliases)
        names = list(sig_anno.keys())
        types = [stringify_typehint(v) for v in sig_anno.values()]
        self.options['argnames'], self.options['argtypes'] = names, types

    def add_anno_to_header(self, sig: str) -> None:
        sourcename = self.get_sourcename()
        self.get_signal_anno()
        argtypes = self.options.get('argtypes')
        argnames = self.options.get('argnames')
        if argtypes:
            argtypes = ','.join(argtypes)
            self.add_line(f'   :argtypes: {argtypes}', sourcename)
        if argnames:
            argnames = ','.join(argnames)
            self.add_line(f'   :argnames: {argnames}', sourcename)

    def add_directive_header(self, sig: str) -> None:
        super().add_directive_header(sig)
        self.add_anno_to_header(sig)


class QtSlotDocumenter(MethodDocumenter):
    """Documenter for methods decorated with ``@Slot`` or ``@asyncSlot``
    """
    objtype = 'qtslot'
    directivetype = 'qtslot'
    priority = MethodDocumenter.priority + 1
    option_spec = dict(MethodDocumenter.option_spec)

    @classmethod
    def can_document_member(
        cls, member: tp.Any, membername: str, isattr: bool, parent: tp.Any
    ) -> bool:
        if not isinstance(parent, ModuleDocumenter) and inspect.isroutine(member):
            decorated = slot_finder.parse_module(parent.real_modname)
            name = safe_getattr(member, '__qualname__', None)
            return name in decorated

        return False

    def add_directive_header(self, sig: str) -> None:
        super().add_directive_header(sig)
        decorated = slot_finder.parse_module(self.real_modname)
        key = '.'.join(self.objpath)
        decorator = decorated[key]
        if 'async' in decorator:
            self.add_line('   :async:', self.get_sourcename())



class QtPropertyDocumenter(AttributeDocumenter):
    """Documenter for QtCore.Property definitions
    """
    objtype = 'qtproperty'
    directive = 'qtproperty'
    priority = AttributeDocumenter.priority + 1
    option_spec = dict(AttributeDocumenter.option_spec)

    @classmethod
    def can_document_member(
        cls, member: tp.Any, membername: str, isattr: bool, parent: tp.Any
    ) -> bool:

        if not isinstance(parent, ModuleDocumenter):
            if isinstance(member, Property):
                return True
        return False

    def add_directive_header(self, sig: str) -> None:
        self.options.no_value = True
        super().add_directive_header(sig)
        sourcename = self.get_sourcename()

        tp_anno = get_type_hints(self.parent, None, self.config.autodoc_type_aliases)
        if self.objpath[-1] in tp_anno:
            return
        annotations = safe_getattr(self.parent, '__annotations__', {})
        obj_anno = annotations.get(self.objpath[-1])
        if obj_anno is not None:
            objrepr = stringify_typehint(obj_anno)
            self.add_line(f'   :type: {objrepr}', sourcename)


class QtSignalDirective(PyMethod):
    option_spec = PyMethod.option_spec.copy()
    option_spec['argnames'] = directives.unchanged
    option_spec['argtypes'] = directives.unchanged

    def add_args_from_options(self, signode: desc_signature) -> None:
        params = addnodes.desc_parameterlist()
        argnames = self.options.get('argnames', [])
        argtypes = self.options.get('argtypes', [])
        if len(argtypes):
            argnames, argtypes = list_option(argnames), list_option(argtypes)
            arglist = ', '.join([
                f'{argname}: {argtype}' for argname, argtype in zip(argnames, argtypes)
            ])
            params = _parse_arglist(arglist, self.env)
            signode += params
        else:
            signode.extend([
                addnodes.desc_sig_punctuation('', '('),
                addnodes.desc_sig_punctuation('', ')'),
            ])

    def get_signature_prefix(self, sig: str) -> tp.List[nodes.Node]:
        return [
            qt_type_to_xref(FULL_NAMES[Signal], self.env, suppress_prefix=True),
            addnodes.desc_sig_space(),
        ]

    def handle_signature(self, sig: str, signode: desc_signature) -> tp.Tuple[str, str]:
        fullname, prefix = super().handle_signature(sig, signode)
        self.add_args_from_options(signode)
        return fullname, prefix

    def needs_arglist(self) -> bool:
        return False


class QtSlotDirective(PyMethod):
    def get_signature_prefix(self, sig: str) -> tp.List[nodes.Node]:
        prefix = []
        if 'async' in self.options:
            prefix.extend([
                nodes.Text('async'),
                addnodes.desc_sig_space(),
            ])
        prefix.extend([
            qt_type_to_xref(FULL_NAMES[Slot], self.env, suppress_prefix=True),
            addnodes.desc_sig_space()
        ])
        return prefix


class QtPropertyDirective(PyAttribute):
    def get_signature_prefix(self, sig: str) -> tp.List[nodes.Node]:
        return [
            qt_type_to_xref(FULL_NAMES[Property], self.env, suppress_prefix=True),
            addnodes.desc_sig_space(),
        ]



def setup(app: Sphinx) -> None:
    app.setup_extension('sphinx.ext.autodoc')
    app.add_autodocumenter(QtSignalDocumenter)
    app.add_autodocumenter(QtSlotDocumenter)
    app.add_autodocumenter(QtPropertyDocumenter)

    app.setup_extension('sphinx.directives')
    sig_role = PyXRefRole()
    slot_role = PyXRefRole()
    prop_role = PyXRefRole()
    sig_obj_type = ObjType(_('QtSignal'), 'qtsignal', 'attr', 'obj')
    slot_obj_type = ObjType(_('QtSlot'), 'qtslot', 'meth', 'obj')
    prop_obj_type = ObjType(_('QtProperty'), 'qtproperty', 'attr', 'obj')

    app.add_directive_to_domain('py', 'qtsignal', QtSignalDirective)
    app.add_directive_to_domain('py', 'qtslot', QtSlotDirective)
    app.add_directive_to_domain('py', 'qtproperty', QtPropertyDirective)
    app.add_role_to_domain('py', 'qtsignal', sig_role)
    app.add_role_to_domain('py', 'qtslot', slot_role)
    app.add_role_to_domain('py', 'qtproperty', prop_role)

    object_types = app.registry.domain_object_types.setdefault('py', {})
    object_types['qtsignal'] = sig_obj_type
    object_types['qtslot'] = slot_obj_type
    object_types['qtproperty'] = prop_obj_type

    return {'version': '0.1', 'parallel_read_safe': True}
