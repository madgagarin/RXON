# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import MISSING, fields, is_dataclass
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID


def extract_json_schema(
    schema_type: Any, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any] | None:
    """Helper to extract JSON schema from dict, Dataclass, NamedTuple, or primitives."""
    if schema_type is None:
        return None
    if isinstance(schema_type, dict):
        return schema_type

    if extractor:
        custom_schema = extractor(schema_type)
        if custom_schema is not None:
            return custom_schema

    if is_dataclass(schema_type) and isinstance(schema_type, type):
        properties = {}
        required = []
        for f in fields(schema_type):
            properties[f.name] = _python_type_to_json_schema(f.type)
            if f.default is MISSING and f.default_factory is MISSING and not _is_optional(f.type):
                required.append(f.name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    if hasattr(schema_type, "_fields") and hasattr(schema_type, "__annotations__"):
        properties = {}
        required = list(schema_type._fields)
        defaults = getattr(schema_type, "_field_defaults", {})
        hints = get_type_hints(schema_type)
        for field_name in schema_type._fields:
            field_type = hints.get(field_name, Any)
            properties[field_name] = _python_type_to_json_schema(field_type)
            if field_name in defaults or _is_optional(field_type):
                if field_name in required:
                    required.remove(field_name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    try:
        return _python_type_to_json_schema(schema_type)
    except Exception:
        return None


def _is_optional(tp: Any) -> bool:
    """Checks if a type is Optional[T] or T | None."""
    if isinstance(tp, UnionType):
        return type(None) in get_args(tp)
    origin = get_origin(tp)
    return origin is Union and type(None) in get_args(tp)


def _python_type_to_json_schema(tp: Any) -> dict[str, Any]:
    """Recursively converts Python types to JSON Schema fragments."""
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        None: "null",
        type(None): "null",
        UUID: "string",
    }

    if tp in mapping:
        return {"type": mapping[tp]}

    if isinstance(tp, UnionType):
        return {"anyOf": [_python_type_to_json_schema(a) for a in get_args(tp)]}

    origin = get_origin(tp)
    args = get_args(tp)

    if origin is Union:
        return {"anyOf": [_python_type_to_json_schema(a) for a in args]}

    if origin is list or tp is list:
        item_type = args[0] if args else Any
        return {"type": "array", "items": _python_type_to_json_schema(item_type)}

    if origin is dict or tp is dict:
        return {"type": "object"}

    if isinstance(tp, type) and (is_dataclass(tp) or hasattr(tp, "_fields")):
        nested = extract_json_schema(tp)
        return nested if nested else {"type": "object"}

    return {"type": "string"}


def validate_data(data: Any, schema: dict[str, Any] | None) -> tuple[bool, str | None]:
    """Basic JSON Schema validation (types, required, properties, array items, anyOf, null)."""
    if schema is None:
        return True, None

    if "anyOf" in schema:
        errors = []
        for sub_schema in schema["anyOf"]:
            is_valid, error = validate_data(data, sub_schema)
            if is_valid:
                return True, None
            errors.append(error)
        return False, f"Value does not match any schemas: {'; '.join(filter(None, errors))}"

    schema_type = schema.get("type")
    if data is None:
        return (True, None) if schema_type == "null" else (False, f"Expected {schema_type}, got null")

    if schema_type == "object":
        if not isinstance(data, dict):
            return False, f"Expected object, got {type(data).__name__}"
        required = schema.get("required") or []
        for field in required:
            if field not in data:
                return False, f"Missing required field: '{field}'"
        properties = schema.get("properties", {})
        for field, value in data.items():
            if field in properties:
                is_valid, error = validate_data(value, properties[field])
                if not is_valid:
                    return False, f"Field '{field}': {error}"
            elif schema.get("additionalProperties") is False:
                return False, f"Unexpected field: '{field}'"

    elif schema_type == "array":
        if not isinstance(data, (list, tuple)):
            return False, f"Expected array, got {type(data).__name__}"
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(data):
                is_valid, error = validate_data(item, items_schema)
                if not is_valid:
                    return False, f"Item at index {i}: {error}"

    elif schema_type == "string":
        if not isinstance(data, str):
            return False, f"Expected string, got {type(data).__name__}"
    elif schema_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            return False, f"Expected integer, got {type(data).__name__}"
    elif schema_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            return False, f"Expected number, got {type(data).__name__}"
    elif schema_type == "boolean":
        if not isinstance(data, bool):
            return False, f"Expected boolean, got {type(data).__name__}"

    return True, None


def extract_schema_from_func(
    func: Any, arg_name: str, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any] | None:
    """Extracts JSON schema from a specific argument of a function."""
    try:
        hints = get_type_hints(func)
        param_hint = hints.get(arg_name)
        if param_hint:
            return extract_json_schema(param_hint, extractor=extractor)
    except Exception:
        pass
    return None


def extract_output_schema_from_func(
    func: Any, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any] | None:
    """Extracts JSON schema from the return type of a function."""
    try:
        hints = get_type_hints(func)
        return_hint = hints.get("return")
        if return_hint:
            if get_origin(return_hint) is dict or return_hint is dict:
                return None
            return extract_json_schema(return_hint, extractor=extractor)
    except Exception:
        pass
    return None


def extract_skill_contract(
    blueprint: Any, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any]:
    """Analyzes a blueprint or function and returns its inferred interface contract."""
    input_schema = None
    if hasattr(blueprint, "start_state") and blueprint.start_state:
        start_handler = blueprint.handlers.get(blueprint.start_state)
        if not start_handler and hasattr(blueprint, "conditional_handlers"):
            for ch in blueprint.conditional_handlers:
                if ch.state == blueprint.start_state:
                    start_handler = ch.func
                    break
        if start_handler:
            input_schema = extract_schema_from_func(start_handler, "initial_data", extractor=extractor)

    end_schemas = []
    if hasattr(blueprint, "end_states"):
        for state in blueprint.end_states:
            handler = blueprint.handlers.get(state)
            if handler:
                schema = extract_output_schema_from_func(handler, extractor=extractor)
                if schema and schema not in end_schemas:
                    end_schemas.append(schema)

    output_schema = None
    if len(end_schemas) == 1:
        output_schema = end_schemas[0]
    elif len(end_schemas) > 1:
        output_schema = {"anyOf": end_schemas}

    output_statuses = set()
    if hasattr(blueprint, "_get_all_transitions"):
        if hasattr(blueprint, "end_states"):
            output_statuses.update(blueprint.end_states)
        if not output_statuses:
            output_statuses.update(["success", "failure"])

    return {
        "input_schema": input_schema,
        "output_schema": output_schema,
        "events_schema": getattr(blueprint, "events_schema", None),
        "output_statuses": sorted(output_statuses) if output_statuses else ["success", "failure"],
    }
