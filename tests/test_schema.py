# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Optional, Union

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
    api_key: Optional[str] = None


@dataclass
class NestedConfig:
    name: str
    config: SimpleConfig
    tags: list[str]


def test_extract_json_schema_primitives():
    assert extract_json_schema(str) == {"type": "string"}
    assert extract_json_schema(int) == {"type": "integer"}
    assert extract_json_schema(float) == {"type": "number"}
    assert extract_json_schema(bool) == {"type": "boolean"}
    assert extract_json_schema(None) is None


def test_extract_json_schema_optional():
    # Optional[str] or str | None
    schema = extract_json_schema(Optional[str])
    assert "anyOf" in schema
    assert {"type": "string"} in schema["anyOf"]
    assert {"type": "null"} in schema["anyOf"]


def test_extract_json_schema_union():
    schema = extract_json_schema(Union[int, str])
    assert "anyOf" in schema
    assert {"type": "integer"} in schema["anyOf"]
    assert {"type": "string"} in schema["anyOf"]


def test_extract_json_schema_dataclass():
    schema = extract_json_schema(SimpleConfig)
    assert schema["type"] == "object"
    assert schema["properties"]["enabled"] == {"type": "boolean"}
    assert schema["properties"]["retry_count"] == {"type": "integer"}
    assert schema["properties"]["api_key"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert "enabled" in schema["required"]
    assert "retry_count" not in schema["required"]  # Has default


def test_extract_json_schema_nested():
    schema = extract_json_schema(NestedConfig)
    assert schema["properties"]["config"]["type"] == "object"
    assert schema["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}


def test_validate_data_success():
    schema = extract_json_schema(SimpleConfig)
    data = {"enabled": True, "retry_count": 5}
    is_valid, error = validate_data(data, schema)
    assert is_valid is True
    assert error is None


def test_validate_data_missing_required():
    schema = extract_json_schema(SimpleConfig)
    data = {"retry_count": 5}  # Missing 'enabled'
    is_valid, error = validate_data(data, schema)
    assert is_valid is False
    assert "Missing required field: 'enabled'" in error


def test_validate_data_wrong_type():
    schema = extract_json_schema(SimpleConfig)
    data = {"enabled": "yes"}  # Should be bool
    is_valid, error = validate_data(data, schema)
    assert is_valid is False
    assert "Field 'enabled': Expected boolean" in error


def test_validate_data_additional_props():
    schema = extract_json_schema(SimpleConfig)
    data = {"enabled": True, "extra": 123}
    is_valid, error = validate_data(data, schema)
    assert is_valid is False
    assert "Unexpected field: 'extra'" in error


def test_extract_from_func():
    def my_skill(initial_data: SimpleConfig) -> NestedConfig:
        pass

    input_schema = extract_schema_from_func(my_skill, "initial_data")
    assert input_schema["properties"]["enabled"] == {"type": "boolean"}

    output_schema = extract_output_schema_from_func(my_skill)
    assert output_schema["properties"]["config"]["type"] == "object"
