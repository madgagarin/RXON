# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from rxon.utils import calculate_dict_hash, json_dumps, to_dict


class Color(Enum):
    RED = "red"
    BLUE = "blue"


class Child(NamedTuple):
    id: int


@dataclass(slots=True)
class Parent:
    name: str
    child: Child
    color: Color
    tags: list[str]


def test_to_dict_complex_nested():
    obj = Parent(name="test", child=Child(1), color=Color.RED, tags=["a", "b"])
    expected = {"name": "test", "child": {"id": 1}, "color": "red", "tags": ["a", "b"]}
    assert to_dict(obj) == expected


def test_to_dict_list_of_objects():
    data = [Child(1), Child(2)]
    expected = [{"id": 1}, {"id": 2}]
    assert to_dict(data) == expected


def test_json_dumps():
    data = {"a": 1, "b": [2, 3]}
    res = json_dumps(data)
    assert res == '{"a":1,"b":[2,3]}'
    # Ensure it handles NamedTuples
    assert "id" in json_dumps(Child(5))


def test_calculate_dict_hash_stability():
    # Order of keys in dict should not affect hash
    d1 = {"a": 1, "b": 2, "c": {"x": 10, "y": 20}}
    d2 = {"c": {"y": 20, "x": 10}, "b": 2, "a": 1}

    h1 = calculate_dict_hash(d1)
    h2 = calculate_dict_hash(d2)

    assert h1 == h2
    assert len(h1) == 64  # SHA256 length


def test_calculate_dict_hash_diff():
    h1 = calculate_dict_hash({"a": 1})
    h2 = calculate_dict_hash({"a": 2})
    assert h1 != h2


def test_to_dict_recursive_mixed():
    data = {"item": Child(10), "meta": [Color.BLUE, {"nested": Parent("p", Child(0), Color.RED, [])}]}
    result = to_dict(data)
    assert result["item"]["id"] == 10
    assert result["meta"][0] == "blue"
    assert result["meta"][1]["nested"]["name"] == "p"
