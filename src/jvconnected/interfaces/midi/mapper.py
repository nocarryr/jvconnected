from loguru import logger

from typing import Any, Union, Dict, Sequence, Optional, ClassVar
import dataclasses
from dataclasses import dataclass

@dataclass
class Map:
    name: str = ''
    group_name: str = ''
    full_name: str = ''

    map_type: ClassVar[str] = ''
    index: int = -1

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

@dataclass
class ControllerMap(Map):
    controller: int = 0
    map_type: ClassVar[str] = 'controller'

@dataclass
class NoteMap(Map):
    note: int = 0
    map_type: ClassVar[str] = 'note'

@dataclass
class AdjustControllerMap(Map):
    controller: int = 0
    map_type: ClassVar[str] = 'adjust_controller'

MAP_TYPES = {cls.map_type:cls for cls in [ControllerMap, NoteMap, AdjustControllerMap]}

MapOrDict = Union[Map, Dict]

DEFAULT_MAPPING = (
    ControllerMap(group_name='exposure', name='iris_pos', controller=0),
    AdjustControllerMap(group_name='exposure', name='master_black_pos', controller=1),
    AdjustControllerMap(group_name='exposure', name='gain_pos', controller=2),
    ControllerMap(group_name='paint', name='red_normalized', controller=3),
    ControllerMap(group_name='paint', name='blue_normalized', controller=4),
    AdjustControllerMap(group_name='paint', name='detail_pos', controller=5),
    NoteMap(group_name='tally', name='preview', note=126),
    NoteMap(group_name='tally', name='program', note=127),
)

class MidiMapper:
    """Container for MIDI mapping definitions
    """
    def __init__(self, maps: Optional[Sequence[MapOrDict]] = None):
        self.map = {}
        self.map_grouped = {}
        self.map_by_index = {}
        if maps is None:
            maps = DEFAULT_MAPPING
        for map_obj in maps:
            self.add_map(map_obj)

    def add_map(self, map_obj: Union[Map, Dict]) -> Map:
        if isinstance(map_obj, dict):
            map_type = map_obj.pop('map_type')
            full_name = map_obj.pop('full_name')
            map_obj = self.create_map(map_type, full_name, **map_obj)
        self.add_map_obj(map_obj)
        return map_obj

    def create_map(self, map_type: str, full_name: str, **kwargs) -> Map:
        """Create a :class:`Map` with the given arguments and add it

        Arguments:
            map_type (str): The map type to add
            full_name (str):

        """
        cls = MAP_TYPES[map_type]
        kw = kwargs.copy()
        # _ = kwargs.pop('name', None)
        # _ = kwargs.pop('group_name', None)
        kw['full_name'] = full_name
        obj = cls(**kw)
        self.add_map_obj(obj)
        return obj

    def add_map_obj(self, map_obj: Map):
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
        return self.map.get(full_name)

    def __getitem__(self, full_name: str) -> Map:
        return self.map[full_name]

    def keys(self):
        for grp_key in sorted(self.map_grouped.keys()):
            d = self.map_grouped[grp_key]
            for key in sorted(d.keys()):
                yield d[key].full_name

    def values(self):
        for key in self:
            yield self[key]

    def items(self):
        for key in self:
            yield key, self[key]

    def iter_indexed(self):
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
