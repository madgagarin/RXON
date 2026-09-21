# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from enum import Enum
from logging import getLogger
from re import match as re_match
from re import sub as re_sub
from threading import Lock
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from fastjsonschema import JsonSchemaValueException
from fastjsonschema import compile as compile_schema
from msgspec import NODEFAULT, Struct
from msgspec.structs import fields as msgspec_fields
from orjson import OPT_SORT_KEYS
from orjson import dumps as orjson_dumps

logger = getLogger(__name__)


class Header:
    """Marker annotation for HTTP request headers in schemas."""

    __slots__ = ("name", "default", "is_header")

    def __init__(self, name: str, default: Any = ...):
        self.name = name
        self.default = default
        self.is_header = True

    def __repr__(self) -> str:
        return f"Header({self.name!r})"


def extract_json_schema(
    schema_type: Any, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any] | None:
    if schema_type is None:
        return None
    if isinstance(schema_type, dict):
        return schema_type

    if extractor:
        custom_schema = extractor(schema_type)
        if custom_schema is not None:
            return custom_schema

    # Duck typing for Pydantic v2
    if hasattr(schema_type, "model_json_schema") and callable(schema_type.model_json_schema):
        try:
            return schema_type.model_json_schema()
        except Exception:
            pass

    # Duck typing for Pydantic v1
    if hasattr(schema_type, "schema") and callable(schema_type.schema):
        try:
            return schema_type.schema()
        except Exception:
            pass

    # msgspec Struct
    if isinstance(schema_type, type) and issubclass(schema_type, Struct):
        properties = {}
        required = []
        for field_info in msgspec_fields(schema_type):
            if field_info.name.startswith("_"):
                continue
            properties[field_info.name] = _python_type_to_json_schema(field_info.type)
            if field_info.default is NODEFAULT and not _is_optional(field_info.type):
                required.append(field_info.name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    # dataclasses
    if isinstance(schema_type, type) and dataclasses.is_dataclass(schema_type):
        properties = {}
        required = []
        for f in dataclasses.fields(schema_type):
            if f.name.startswith("_"):
                continue
            properties[f.name] = _python_type_to_json_schema(f.type)
            if (
                f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING
                and not _is_optional(f.type)
            ):
                required.append(f.name)
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
    if isinstance(tp, UnionType):
        return type(None) in get_args(tp)
    origin = get_origin(tp)
    return origin is Union and type(None) in get_args(tp)


def _python_type_to_json_schema(tp: Any) -> dict[str, Any]:
    if tp is Any:
        return {}

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

    if isinstance(tp, type) and issubclass(tp, Enum):
        return {"type": "string", "enum": [e.value for e in tp]}

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

    if get_origin(tp) is Annotated:
        return _python_type_to_json_schema(get_args(tp)[0])

    if hasattr(tp, "model_json_schema") and callable(tp.model_json_schema):
        try:
            return tp.model_json_schema()
        except Exception:
            pass

    if hasattr(tp, "schema") and callable(tp.schema):
        try:
            return tp.schema()
        except Exception:
            pass

    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        nested = extract_json_schema(tp)
        return nested if nested else {"type": "object"}

    if isinstance(tp, type) and issubclass(tp, Struct):
        nested = extract_json_schema(tp)
        return nested if nested else {"type": "object"}

    return {"type": "string"}


def _get_val_by_path(data: Any, path: str) -> Any:
    if not path:
        return data
    parts = path.split(".")
    curr = data
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        elif isinstance(curr, list) and p.isdigit() and int(p) < len(curr):
            curr = curr[int(p)]
        else:
            return None
    return curr


def translate_error(msg: str, data: Any) -> str:
    msg = re_sub(r"\[(\d+)\]", r".\1", msg)

    if "cannot be validated by any definition" in msg or "anyOf" in msg:
        return "Value does not match any schemas"

    m = re_match(r"data(\.(.*)|) must be one of (.*)", msg)
    if m:
        _, path, enum_list = m.groups()
        val = _get_val_by_path(data, path)
        prefix = ""
        if path:
            parts = path.split(".")
            prefix = "".join(f"Field '{p}': " for p in parts)
        return f"{prefix}Value '{val}' is not allowed. Must be one of: {enum_list}"

    m = re_match(r"data(.*) must contain \[(.*)\]", msg)
    if m:
        path, field = m.groups()
        field_name = field.strip("'\"")
        prefix = ""
        if path:
            parts = [p.strip(".") for p in path.split(".") if p.strip(".")]
            if parts:
                prefix = "".join(f"Field '{p}': " for p in parts)
        return f"{prefix}Missing required field: '{field_name}'"

    m = re_match(r"data(.*) must not contain \{(.*)\} properties", msg)
    if m:
        path, field = m.groups()
        field_name = field.strip("'\"")
        prefix = ""
        if path:
            parts = [p.strip(".") for p in path.split(".") if p.strip(".")]
            if parts:
                prefix = "".join(f"Field '{p}': " for p in parts)
        return f"{prefix}Unexpected field: '{field_name}'"

    m = re_match(r"data\.(.*) must be (.*)", msg)
    if m:
        path, expected = m.groups()
        parts = path.split(".")
        prefix = "".join(f"Field '{p}': " for p in parts[:-1])
        last_field = parts[-1]

        if last_field.isdigit():
            if len(parts) >= 2:
                array_field = parts[-2]
                prefix = "".join(f"Field '{p}': " for p in parts[:-2])
                return f"{prefix}Field '{array_field}': Item at index {last_field}: Expected {expected}"
            else:
                return f"Item at index {last_field}: Expected {expected}"

        val = _get_val_by_path(data, path)
        if val is None:
            return f"{prefix}Field '{last_field}': Expected {expected}, got null"
        return f"{prefix}Field '{last_field}': Expected {expected}"

    m = re_match(r"data must be (.*)", msg)
    if m:
        expected = m.group(1)
        if data is None:
            return f"Expected {expected}, got null"
        return f"Expected {expected}"

    return msg


_validators_cache: dict[bytes, Any] = {}
_cache_lock = Lock()
_MAX_VALIDATOR_CACHE_SIZE: int = 1024


def get_compiled_validator(
    schema: dict[str, Any] | None,
    skill_name: str | None = None,
    schema_type: str = "input",
) -> Any | None:
    """Returns a compiled fastjsonschema validator using a bounded thread-safe cache."""
    if not schema:
        return None

    try:
        schema_key = orjson_dumps(schema, option=OPT_SORT_KEYS)
    except Exception:
        schema_key = str(sorted(schema.items())).encode("utf-8")

    validator = _validators_cache.get(schema_key)
    if validator is not None:
        return validator

    with _cache_lock:
        validator = _validators_cache.get(schema_key)
        if validator is None:
            try:
                validator = compile_schema(schema)
                if len(_validators_cache) >= _MAX_VALIDATOR_CACHE_SIZE:
                    _validators_cache.pop(next(iter(_validators_cache)))
                _validators_cache[schema_key] = validator
            except Exception as e:
                if skill_name:
                    logger.warning(
                        "Failed to compile %s schema for skill '%s': %s",
                        schema_type,
                        skill_name,
                        e,
                    )
                else:
                    logger.warning("Failed to compile schema: %s", e)
                return None
        return validator


def validate_data(data: Any, schema: dict[str, Any] | None) -> tuple[bool, str | None]:
    if schema is None or not schema:
        return True, None

    validator = get_compiled_validator(schema)
    if validator is None:
        return False, "Failed to compile schema"

    try:
        validator(data)
        return True, None
    except JsonSchemaValueException as e:
        return False, translate_error(e.message, data)
    except Exception as e:
        return False, str(e)


def extract_input_schema_from_func(
    func: Any, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any] | None:
    """Extracts input JSON schema from a handler's signature.

    Supports arbitrary parameter names, Pydantic models, msgspec Structs,
    dataclasses, scalars, and composite multi-parameter signatures.
    Framework arguments (ctx, context, task_files, actions, self, cls) and Header(...)
    annotated parameters are automatically excluded.
    """
    if not callable(func):
        return None

    try:
        sig = inspect.signature(func)
    except Exception:
        return None

    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}

    system_param_names = {
        "ctx",
        "context",
        "task_files",
        "actions",
        "self",
        "cls",
        "job_id",
        "current_state",
        "state",
        "data_stores",
        "client",
    }
    business_params: list[tuple[str, inspect.Parameter, Any]] = []

    for name, param in sig.parameters.items():
        if name in system_param_names:
            continue

        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        ann = hints.get(name, param.annotation)

        if get_origin(ann) is Annotated:
            meta_args = get_args(ann)[1:]
            if any(
                getattr(m, "__class__", type(m)).__name__ == "Header"
                or getattr(m, "is_header", False)
                for m in meta_args
            ):
                continue

        business_params.append((name, param, ann))

    if not business_params:
        return None

    def _is_structured_model(tp: Any) -> bool:
        if get_origin(tp) is Annotated:
            tp = get_args(tp)[0]
        if not isinstance(tp, type):
            return False
        return (
            issubclass(tp, Struct)
            or hasattr(tp, "model_json_schema")
            or hasattr(tp, "schema")
            or dataclasses.is_dataclass(tp)
        )

    # 1 parameter
    if len(business_params) == 1:
        name, param, ann = business_params[0]
        if name in ("initial_data", "input") and (
            ann is inspect.Parameter.empty or ann is Any or ann is dict or get_origin(ann) is dict
        ):
            return None

        actual_type = get_args(ann)[0] if get_origin(ann) is Annotated else ann

        if _is_structured_model(actual_type):
            return extract_json_schema(actual_type, extractor=extractor)

        prop_schema = extract_json_schema(ann, extractor=extractor) or {"type": "string"}
        required = [name] if param.default == inspect.Parameter.empty else []
        return {
            "type": "object",
            "properties": {name: prop_schema},
            "required": required,
            "additionalProperties": False,
        }

    # >= 2 parameters: composite schema
    properties = {}
    required = []
    for name, param, ann in business_params:
        actual_type = get_args(ann)[0] if get_origin(ann) is Annotated else ann
        if actual_type is inspect.Parameter.empty or actual_type is Any:
            prop_schema = {}
        else:
            prop_schema = extract_json_schema(actual_type, extractor=extractor) or {}
        properties[name] = prop_schema
        if param.default == inspect.Parameter.empty:
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def extract_schema_from_func(
    func: Any, arg_name: str, extractor: Callable[[Any], dict[str, Any] | None] | None = None
) -> dict[str, Any] | None:
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
    try:
        hints = get_type_hints(func)
        return_hint = hints.get("return")
        if return_hint is None or return_hint is type(None):
            return None
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
            input_schema = extract_input_schema_from_func(start_handler, extractor=extractor)
            if input_schema is None:
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
