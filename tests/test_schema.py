# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import NamedTuple

from rxon.schema import (
    extract_json_schema,
    extract_output_schema_from_func,
    extract_schema_from_func,
    validate_data,
)


@dataclass
class SimpleConfig:
    enabled: bool
    retry_count: int = 3
    api_key: str | None = None


@dataclass
class NestedConfig:
    name: str
    config: SimpleConfig
    tags: list[str]


class NTConfig(NamedTuple):
    name: str
    port: int = 8080
    debug: bool | None = None


def test_extract_json_schema_primitives():
    assert extract_json_schema(str) == {"type": "string"}
    assert extract_json_schema(int) == {"type": "integer"}
    assert extract_json_schema(float) == {"type": "number"}
    assert extract_json_schema(bool) == {"type": "boolean"}
    assert extract_json_schema(None) is None


def test_extract_json_schema_optional():
    schema = extract_json_schema(str | None)
    assert "anyOf" in schema
    assert {"type": "string"} in schema["anyOf"]
    assert {"type": "null"} in schema["anyOf"]


def test_extract_json_schema_union():
    schema = extract_json_schema(int | str)
    assert "anyOf" in schema
    assert {"type": "integer"} in schema["anyOf"]
    assert {"type": "string"} in schema["anyOf"]


def test_extract_json_schema_dataclass():
    schema = extract_json_schema(SimpleConfig)
    assert schema["type"] == "object"
    assert schema["properties"]["enabled"] == {"type": "boolean"}
    assert schema["properties"]["retry_count"] == {"type": "integer"}
    assert "enabled" in schema["required"]
    assert "retry_count" not in schema["required"]


def test_extract_json_schema_namedtuple():
    schema = extract_json_schema(NTConfig)
    assert schema["type"] == "object"
    assert schema["properties"]["name"] == {"type": "string"}
    assert "name" in schema["required"]
    assert "port" not in schema["required"]
    assert "debug" not in schema["required"]


def test_validate_data_negative():
    schema = extract_json_schema(NTConfig)

    # 1. Wrong type for primitive
    is_valid, err = validate_data({"name": 123}, schema)
    assert not is_valid
    assert "Field 'name': Expected string" in err

    # 2. Missing required field
    is_valid, err = validate_data({"port": 9000}, schema)
    assert not is_valid
    assert "Missing required field: 'name'" in err

    # 3. Unexpected field (additionalProperties: False)
    is_valid, err = validate_data({"name": "test", "extra": True}, schema)
    assert not is_valid
    assert "Unexpected field: 'extra'" in err

    # 4. Null when not allowed
    is_valid, err = validate_data({"name": None}, schema)
    assert not is_valid
    assert "Field 'name': Expected string, got null" in err


def test_validate_nested_negative():
    schema = extract_json_schema(NestedConfig)

    # Wrong type in nested object
    data = {
        "name": "root",
        "config": {"enabled": "not-a-bool"},  # Error here
        "tags": ["a", "b"],
    }
    is_valid, err = validate_data(data, schema)
    assert not is_valid
    assert "Field 'config': Field 'enabled': Expected boolean" in err

    # Wrong type in array
    data2 = {
        "name": "root",
        "config": {"enabled": True},
        "tags": ["a", 1],  # Error here
    }
    is_valid, err = validate_data(data2, schema)
    assert not is_valid
    assert "Field 'tags': Item at index 1: Expected string" in err


def test_extract_from_func():
    def my_skill(initial_data: SimpleConfig) -> NTConfig:
        return NTConfig(name="dummy")

    input_schema = extract_schema_from_func(my_skill, "initial_data")
    assert input_schema["properties"]["enabled"] == {"type": "boolean"}

    output_schema = extract_output_schema_from_func(my_skill)
    assert output_schema["properties"]["name"] == {"type": "string"}
