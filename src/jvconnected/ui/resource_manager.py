from loguru import logger
import importlib
from typing import Optional, Dict, Tuple
from types import ModuleType

#: Names of resource modules to load
rc_modnames: Tuple[str] = ('rc_images', 'rc_qml', 'rc_resources', 'rc_style')

#: Mapping of loaded resource modules by name
rc_modules: Dict[str, ModuleType] = {}

#: True if all resource modules have been loaded
ready: bool = False


_rc_build_fn_names = {
    'rc_images':'build_images',
    'rc_qml':'pack_qml',
    'rc_resources':'build_fa',
    'rc_style':'build_style',
}

build_qrc: Optional[ModuleType] = None

def _get_builder() -> ModuleType:
    global build_qrc
    if build_qrc is not None:
        return build_qrc
    try:
        from jvconnected.ui.tools import build_qrc as mod
    except ImportError as exc:
        logger.exception(exc)
        mod = None
        raise
    build_qrc = mod
    return build_qrc

def load_module(name: str) -> ModuleType:
    """Attempt to load or reload a resource module and place it in :attr:`rc_modules`
    """
    cur_module = rc_modules.get(name)
    if cur_module is not None:
        logger.debug(f'reloading {name} module')
        cur_module.qCleanupResources()
        del rc_modules[name]
        mod = importlib.reload(cur_module)
    else:
        mod = importlib.import_module(f'.{name}', 'jvconnected.ui')
    rc_modules[name] = mod
    return mod

def load() -> bool:
    """Load all modules in :attr:`rc_modnames`
    """
    global ready
    _ready = True
    for name in rc_modnames:
        if name in rc_modules:
            continue
        try:
            load_module(name)
        except ModuleNotFoundError:
            _ready = False
            logger.debug(f'Could not load {name} module')
    ready = _ready
    return ready

def build_missing() -> bool:
    """Build any missing resource modules using :mod:`~jvconnected.ui.tools.build_qrc`
    """
    global ready
    if ready:
        return
    ready = False
    missing = [name for name in rc_modnames if name not in rc_modules]
    logger.info(f'Build missing resources: {missing}')

    _get_builder()

    for name in missing:
        fn_name = _rc_build_fn_names[name]
        logger.debug(f'building {name}: build_qrc.{fn_name}()')
        fn = getattr(build_qrc, fn_name)
        fn()
        load_module(name)
    ready = True
    logger.success('Resources built')
    return ready
