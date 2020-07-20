import string

import pytest

from jvconnected.utils import IndexedDict

@pytest.fixture
def fakekeys():
    return [c for c in string.ascii_lowercase]

@pytest.fixture
def fakeitems(fakekeys):
    return {c:f'{c}.{i}' for i, c in enumerate(fakekeys)}
    # return {k:v for k,v in}

def test_insertion(fakeitems):

    d = IndexedDict()

    inserted = []
    for key, val in fakeitems.items():
        i = d.add(key, val)
        inserted.append((key, val, i))

    for i in d.iter_consecutive_indices():
        key, val, j = inserted[i]
        assert i == j
        assert d[key] == d.get(key) == d.get_by_index(j) == val
        assert d.get_item_index(key) == j

    for key, val, i in inserted:
        assert d[key] == val
        assert d.get(key) == val
        assert d.get_by_index(i) == val
        assert d.get_item_index(key) == i

    expected_len = len(inserted)
    assert len(d) == expected_len

    print('add foo.bar.1')

    d.add('foo', 'bar', 1)
    expected_len += 1

    assert d['foo'] == d.get('foo') == 'bar'
    assert d.get_by_index(1) == 'bar'
    assert d.get_item_index('foo') == 1

    assert len(d) == expected_len

    for key, val, i in inserted:
        if i == 1:
            continue
        elif i > 0:
            i += 1
        # print(key, val, i)
        assert d[key] == d.get(key) == d.get_by_index(i) == val
        assert d.get_item_index(key) == i

    print('change foo.index to 10')
    d.change_item_index('foo', 10)
    assert d['foo'] == d.get('foo') == 'bar'
    assert d.get_by_index(10) == 'bar'
    assert d.get_item_index('foo') == 10

    for i in range(len(inserted)):
        key, val, j = inserted[i]
        if i > 0:
            j += 1
        if i >= 10:
            j += 1
        if j == 10:
            continue
        # print(key, val, i, j)
        assert d[key] == val
        assert d.get(key) == val
        assert d.get_by_index(j) == val
        assert d.get_item_index(key) == j

    assert len(d) == expected_len
    max_index = max(d.iter_indices())

    foobar_index = max_index + 1

    d.change_item_index('foo', foobar_index)
    assert d['foo'] == d.get('foo') == 'bar'
    assert d.get_by_index(foobar_index) == 'bar'
    assert d.get_item_index('foo') == foobar_index

    assert len(d) == expected_len

    d.compact_indices(max_change=2)

    expected_items = inserted.copy()
    expected_items.append(('foo', 'bar', len(inserted)))

    for key, val, i in expected_items:
        # print(key, val, i)
        assert d[key] == val
        assert d.get(key) == val
        assert d.get_by_index(i) == val
        assert d.get_item_index(key) == i

    for i, j in zip(range(expected_len), d.iter_indices()):
        assert i == j
