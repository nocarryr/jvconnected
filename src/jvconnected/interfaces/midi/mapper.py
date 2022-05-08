from loguru import logger

from typing import (
    Any, Union, Dict, Sequence, Optional, ClassVar, Iterator, Tuple,
)
import dataclasses
from dataclasses import dataclass

@dataclass
class Map:
    """Stores information for mapping MIDI messages to
    :class:`~jvconnected.interfaces.paramspec.ParameterGroupSpec` definitions
    """

    name: str = ''
    """The :attr:`~.paramspec.ParameterSpec.name` of the parameter within its
    :class:`~.paramspec.ParameterGroupSpec`
    """

    group_name: str = ''
    """The :attr:`~.paramspec.ParameterGroupSpec.name` of the
    :class:`~.paramspec.ParameterGroupSpec`
    """

    full_name: str = ''
    """Combination of :attr:`group_name` and :attr:`name`, separated by a "."

    ``"{group_name}.{name}"``
    """

    map_type: ClassVar[str] = ''
    """A unique name to identify subclasses
    """

    index: int = -1
    """The map index

    If not set (or ``-1``), this will be assigned by :class:`MidiMapper` when
    the instance is added to it
    """

    is_14_bit: ClassVar[bool] = False
    """True if the map uses 14 bit values
    """

    def __post_init__(self):
        if not self.full_name:
            self.full_name = '.'.join([self.group_name, self.name])
        else:
            group_name, name = self.full_name.split('.')
            if not self.group_name:
                self.group_name = group_name
            if not self.name:
                self.name = name
            assert self.group_name == group_name
            assert self.name == name

    @classmethod
    def get_class_for_map_type(cls, map_type: str) -> 'Map':
        def iter_subcls(_cls):
            if _cls is not Map:
                yield _cls
            for subcls in _cls.__subclasses__():
                yield from iter_subcls(subcls)
        for _cls in iter_subcls(Map):
            if _cls.map_type == map_type:
                return _cls
        raise ValueError(f'No subclass found with map_type "{map_type}"')

@dataclass
class ControllerMap(Map):
    controller: int = 0 #: The Midi controller number for the mapping
    map_type: ClassVar[str] = 'controller'

@dataclass
class Controller14BitMap(ControllerMap):
    map_type: ClassVar[str] = 'controller/14'
    is_14_bit: ClassVar[bool] = True

    def __post_init__(self):
        super().__post_init__()
        assert self.controller < 0x20

    @property
    def controller_msb(self) -> int:
        """The controller index containing the most-significant 7 bits

        This will always be equal to the :attr:`controller` value
        """
        return self.controller

    @property
    def controller_lsb(self) -> int:
        """The controller index containing the least-significant 7 bits

        Per the MIDI 1.0 specification, this will be :attr:`controller_msb` + 32
        """
        return self.controller + 32


@dataclass
class NoteMap(Map):
    note: int = 0 #: The Midi note number for the mapping
    map_type: ClassVar[str] = 'note'

@dataclass
class AdjustControllerMap(Map):
    controller: int = 0 #: The Midi controller number for the mapping
    map_type: ClassVar[str] = 'adjust_controller'


MapOrDict = Union[Map, Dict]

DEFAULT_MAPPING: Sequence[Map] = (
    Controller14BitMap(group_name='exposure', name='iris_pos', controller=0),
    AdjustControllerMap(group_name='exposure', name='master_black_pos', controller=1),
    AdjustControllerMap(group_name='exposure', name='gain_pos', controller=2),
    ControllerMap(group_name='paint', name='red_normalized', controller=3),
    ControllerMap(group_name='paint', name='blue_normalized', controller=4),
    AdjustControllerMap(group_name='paint', name='detail_pos', controller=5),
    NoteMap(group_name='tally', name='preview', note=126),
    NoteMap(group_name='tally', name='program', note=127),
)
"""Default Midi mapping

The mapping uses the following layout for each camera index (where the channels
will become the camera index)

.. csv-table::
    :header: "Index", "Parameter", "Type", "Controller/Note"
    :widths: auto

    0, "Iris", :class:`Controller14BitMap`, "0 (MSB), 32 (LSB)"
    1, "Master Black", :class:`AdjustControllerMap`, 1
    2, "Gain", :class:`AdjustControllerMap`, 2
    3, "Red Paint", :class:`ControllerMap`, 3
    4, "Blue Paint", :class:`ControllerMap`, 4
    5, "Detail", :class:`AdjustControllerMap`, 5
    6, "PGM Tally", :class:`NoteMap`, 126
    7, "PVW Tally", :class:`NoteMap`, 127

"""

class MidiMapper:
    """Container for MIDI mapping definitions

    Arguments:
        maps: If given, a sequence of either :class:`Map` instances or
            :class:`dicts <dict>` to pass to the :meth:`add_map` method. If not
            provided, the :data:`DEFAULT_MAPPING` will be used.

    The maps can be accessed by their :attr:`~Map.full_name` using :class:`dict`
    methods.

    >>> from jvconnected.interfaces.midi.mapper import MidiMapper, ControllerMap, NoteMap
    >>> mapper = MidiMapper()
    >>> gain = mapper['exposure.gain_pos']
    >>> print(gain)
    AdjustControllerMap(name='gain_pos', group_name='exposure', full_name='exposure.gain_pos', index=2, controller=2)
    >>> mapper.get('exposure.gain_pos')
    AdjustControllerMap(name='gain_pos', group_name='exposure', full_name='exposure.gain_pos', index=2, controller=2)
    >>> 'exposure.gain_pos' in mapper
    True

    When iterating over the mapper, either directly or through the :meth:`keys`,
    :meth:`values` or :meth:`items` methods, the results will be sorted by their
    :attr:`~Map.group_name` then their :attr:`~Map.name` attributes

    >>> [key for key in mapper] #doctest: +NORMALIZE_WHITESPACE
    ['exposure.gain_pos',
     'exposure.iris_pos',
     'exposure.master_black_pos',
     'paint.blue_normalized',
     'paint.detail_pos',
     'paint.red_normalized',
     'tally.preview',
     'tally.program']
    >>> [map_obj.full_name for map_obj in mapper.values()] #doctest: +NORMALIZE_WHITESPACE
    ['exposure.gain_pos',
     'exposure.iris_pos',
     'exposure.master_black_pos',
     'paint.blue_normalized',
     'paint.detail_pos',
     'paint.red_normalized',
     'tally.preview',
     'tally.program']

    Maps can also be sorted by their :attr:`indices <Map.index>` using the
    :meth:`iter_indexed` method

    >>> [map_obj.full_name for map_obj in mapper.iter_indexed()] #doctest: +NORMALIZE_WHITESPACE
    ['exposure.iris_pos',
     'exposure.master_black_pos',
     'exposure.gain_pos',
     'paint.red_normalized',
     'paint.blue_normalized',
     'paint.detail_pos',
     'tally.preview',
     'tally.program']
    >>> [map_obj.index for map_obj in mapper.values()]
    [2, 0, 1, 4, 5, 3, 6, 7]

    By default, MidiMapper will use a set of :data:`predefined maps <DEFAULT_MAPPING>`
    when initialized. This can be overridden by passing a sequence of map definitions
    (or an empty one) when creating it

    >>> mapper = MidiMapper([])
    >>> len(mapper)
    0

    Then use :meth:`add_map` to create maps using a :class:`dict`

    >>> pgm_tally = mapper.add_map(dict(map_type='note', full_name='tally.program', note=127))
    >>> mapper['tally.program']
    NoteMap(name='program', group_name='tally', full_name='tally.program', index=0, note=127)

    Or existing :class:`Map` instances

    >>> pvw_tally = NoteMap(group_name='tally', name='preview', note=126)
    >>> pvw_tally
    NoteMap(name='preview', group_name='tally', full_name='tally.preview', index=-1, note=126)
    >>> mapper.add_map(pvw_tally) #doctest: +IGNORE_RESULT
    >>> mapper['tally.preview']
    NoteMap(name='preview', group_name='tally', full_name='tally.preview', index=1, note=126)
    >>> mapper['tally.preview'] is pvw_tally
    True

    """

    map: Dict[str, Map]
    """The :class:`Map` definitions stored using their :attr:`~Map.full_name`
    as keys
    """

    map_grouped: Dict[str, Dict[str, Map]]
    """The :class:`Map` definitions stored as nested dicts by :attr:`~Map.group_name`
    and :attr:`~Map.name`
    """

    map_by_index: Dict[int, Map]
    """The :class:`Map` definitions stored using their :attr:`~Map.index` as keys
    """
    def __init__(self, maps: Optional[Sequence[MapOrDict]] = None):
        self.map = {}
        self.map_grouped = {}
        self.map_by_index = {}
        if maps is None:
            maps = DEFAULT_MAPPING
        for map_obj in maps:
            self.add_map(map_obj)

    def add_map(self, map_obj: MapOrDict) -> Map:
        """Add or create a :class:`Map` definition

        * If the given argument is a :class:`dict`, it must contain a value for
          "map_type" as described in the :meth:`create_map` method,
          with the remaining items passed as keyword arguments.
        * If the given argument is a :class:`Map` instance, it is added using
          :meth:`add_map_obj`.

        """
        if isinstance(map_obj, dict):
            map_type = map_obj.pop('map_type')
            map_obj = self.create_map(map_type, **map_obj)
        self.add_map_obj(map_obj)
        return map_obj

    def create_map(self, map_type: str, **kwargs) -> Map:
        """Create a :class:`Map` with the given arguments and add it

        Arguments:
            map_type (str): The :attr:`~Map.map_type` of the :class:`Map`
                subclass to create
            **kwargs: Keyword arguments used to create the instance

        """
        cls = Map.get_class_for_map_type(map_type)
        kw = kwargs.copy()
        obj = cls(**kw)
        return obj

    def add_map_obj(self, map_obj: Map):
        """Add an existing :class:`Map` instance
        """
        if map_obj.index == -1 or map_obj.index in self.map_by_index:
            if not len(self):
                map_obj.index = 0
            else:
                map_obj.index = max(self.map_by_index.keys()) + 1
        self.map[map_obj.full_name] = map_obj
        self.map_by_index[map_obj.index] = map_obj
        if map_obj.group_name not in self.map_grouped:
            self.map_grouped[map_obj.group_name] = {}
        self.map_grouped[map_obj.group_name][map_obj.name] = map_obj

    def get(self, full_name: str) -> Optional[Map]:
        """Get the :class:`Map` instance matching the given :attr:`~Map.full_name`

        If not found, ``None`` is returned
        """
        return self.map.get(full_name)

    def __getitem__(self, full_name: str) -> Map:
        return self.map[full_name]

    def keys(self) -> Iterator[str]:
        """Iterate over all the :attr:`~Map.full_name` of all stored instances

        This will be sorted first by :attr:`~Map.group_name`, then by
        :attr:`~Map.name`
        """
        for grp_key in sorted(self.map_grouped.keys()):
            d = self.map_grouped[grp_key]
            for key in sorted(d.keys()):
                yield d[key].full_name

    def values(self) -> Iterator[Map]:
        """Iterate over all stored instances, sorted as described in :meth:`keys`
        """
        for key in self:
            yield self[key]

    def items(self) -> Iterator[Tuple[str, Map]]:
        """Iterate over pairs of :meth:`keys` and :meth:`values`
        """
        for key in self:
            yield key, self[key]

    def iter_indexed(self) -> Iterator[Map]:
        """Iterate over all stored instances, sorted by their :attr:`~Map.index`
        """
        for ix in sorted(self.map_by_index.keys()):
            yield self.map_by_index[ix]

    def __iter__(self):
        return self.keys()

    def __len__(self):
        return len(self.map)

    def __contains__(self, key: str):
        return key in self.map

    def serialize(self):
        d = {'maps':[]}
        for map_obj in self.values():
            _d = dataclasses.asdict(map_obj)
            _d['map_type'] = map_obj.map_type
            d['maps'].append(_d)
        return d
