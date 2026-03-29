# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple
from uuid import UUID, uuid4

import pytest

from rxon.utils import calculate_dict_hash, from_dict, json_dumps, to_dict


class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Point(NamedTuple):
    x: int
    y: int
    label: str | None = None


@dataclass
class Config:
    name: str
    points: list[Point]
    status: Status = Status.ACTIVE
    metadata: dict[str, str] | None = None


def test_to_dict_full():
    p1 = Point(1, 2, "start")
    c = Config(name="test", points=[p1], status=Status.INACTIVE, metadata={"env": "prod"})

    d = to_dict(c)
    assert d["name"] == "test"
    assert d["points"][0]["x"] == 1
    assert d["status"] == "inactive"
    assert d["metadata"]["env"] == "prod"


def test_to_dict_uuid():
    uid = uuid4()
    assert to_dict(uid) == str(uid)


def test_from_dict_full():
    data = {
        "name": "test",
        "points": [{"x": 10, "y": 20, "label": "A"}, {"x": 30, "y": 40}],
        "status": "inactive",
        "metadata": {"key": "val"},
    }

    # Restore dataclass
    c = from_dict(Config, data)
    assert isinstance(c, Config)
    assert len(c.points) == 2
    assert isinstance(c.points[0], Point)
    assert c.points[1].label is None
    assert c.status == Status.INACTIVE


def test_from_dict_negative():
    # 1. Missing required field in NamedTuple
    data = {"x": 1}  # Missing 'y'
    with pytest.raises(ValueError, match="Failed to instantiate Point"):
        from_dict(Point, data)

    # 2. Not a dict
    assert from_dict(Point, "not-a-dict") == "not-a-dict"

    # 3. None input
    assert from_dict(Point, None) is None


def test_json_dumps():
    p = Point(1, 2)
    s = json_dumps(p)
    assert '"x":1' in s
    assert '"y":2' in s


def test_from_dict_extreme_chaos():
    # Expecting a Point (NamedTuple), but getting a string
    data = {"points": "this-should-be-a-list-of-dicts"}
    # from_dict currently fails only on instantiation, so Config will fail because 'name' is missing
    with pytest.raises(ValueError, match="Failed to instantiate Config"):
        from_dict(Config, data)

    # Missing required field in nested restoration
    data2 = {"name": "test", "points": [123]}  # Point expects dict, gets int
    c2 = from_dict(Config, data2)
    assert c2.points == [123]  # _restore_field returns raw if not a dict


def test_from_dict_optional_list():
    @dataclass
    class Root:
        items: list[Point] | None = None

    # Case 1: items is None
    r1 = from_dict(Root, {"items": None})
    assert r1.items is None

    # Case 2: items is list of dicts
    r2 = from_dict(Root, {"items": [{"x": 1, "y": 2}]})
    assert len(r2.items) == 1
    assert r2.items[0].x == 1


def test_from_dict_empty_collections():
    @dataclass
    class Multi:
        tags: list[str] | None = None
        info: dict[str, int] | None = None

    # JSON with nulls
    m1 = from_dict(Multi, {"tags": None, "info": None})
    assert m1.tags is None
    assert m1.info is None

    # JSON with empty collections
    m2 = from_dict(Multi, {"tags": [], "info": {}})
    assert m2.tags == []
    assert m2.info == {}


def test_from_dict_uuid():
    @dataclass
    class Node:
        id: UUID
        tags: list[UUID] | None = None

    uid1 = uuid4()
    uid2 = uuid4()

    data = {"id": str(uid1), "tags": [str(uid2)]}

    node = from_dict(Node, data)
    assert node.id == uid1
    assert isinstance(node.id, UUID)
    assert node.tags[0] == uid2
    assert isinstance(node.tags[0], UUID)


def test_dict_hash():
    d1 = {"a": 1, "b": 2}
    d2 = {"b": 2, "a": 1}
    assert calculate_dict_hash(d1) == calculate_dict_hash(d2)


def test_type_hints_caching():
    from rxon.utils import _get_cached_type_hints

    # Initial call
    hints1 = _get_cached_type_hints(Config)
    assert "points" in hints1

    # Second call should be from cache
    hints2 = _get_cached_type_hints(Config)
    assert hints1 is hints2

    # Different class should have different hints
    hints_other = _get_cached_type_hints(Point)
    assert hints_other is not hints1
    assert "x" in hints_other

    # Verify cache info (if accessible)
    info = _get_cached_type_hints.cache_info()
    assert info.hits > 0
