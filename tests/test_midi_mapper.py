import pytest
import dataclasses
from jvconnected.interfaces.midi import mapper

@pytest.fixture
def replacement_maps():
    orig_maps = mapper.DEFAULT_MAPPING
    new_maps = []
    for m in orig_maps:
        d = dataclasses.asdict(m)
        if isinstance(m, mapper.NoteMap):
            note = m.note
            if note > 120:
                note -= 1
            else:
                note += 1
            # new_m = dataclasses.replace(m, note=note)
            d['note'] = note
        else:
            # new_m = dataclasses.replace(m, controller=m.controller+1)
            d['controller'] = m.controller + 1
        cls = mapper.MAP_TYPES[m.map_type]
        new_m = cls(**d)
        new_maps.append(new_m)
    return tuple(new_maps)


def test_mapper(replacement_maps):
    for m in mapper.DEFAULT_MAPPING:
        assert m.full_name == '.'.join([m.group_name, m.name])

    default_map = mapper.MidiMapper()
    default_serialized = default_map.serialize()
    # print(default_serialized)

    map2 = mapper.MidiMapper(default_serialized['maps'])
    map2_serialized = map2.serialize()

    map3 = mapper.MidiMapper(map2_serialized['maps'])

    # print(map2_serialized)

    # for i, d in enumerate(default_serialized['maps']):
    #     d2 = map2_serialized['maps'][i]
    #     print(d)
    #     print(d2)
    #     assert d == d2
    #
    # assert map2_serialized == default_serialized

    i = 0
    for full_name, m in default_map.items():
        assert default_map[full_name] == default_map.get(full_name)
        assert map2[full_name] == map2.get(full_name)
        assert map3[full_name] == map3.get(full_name)
        assert m == default_map[full_name] == map2[full_name] == map3[full_name]
        i += 1
    assert i == len(mapper.DEFAULT_MAPPING) == len(default_map) == len(map2) == len(map3)


    replacement_map = mapper.MidiMapper(replacement_maps)
    replacement_map_serialized = replacement_map.serialize()

    for m_def in replacement_maps:
        full_name = '.'.join([m_def.group_name, m_def.name])
        assert m_def == replacement_map[full_name] == replacement_map.get(full_name)
