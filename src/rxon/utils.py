# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from functools import lru_cache
from hashlib import sha256
from sys import modules
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from orjson import OPT_NON_STR_KEYS, OPT_SORT_KEYS, dumps, loads

__all__ = [
    "to_dict",
    "from_dict",
    "json_dumps",
    "loads",
    "calculate_dict_hash",
]


@lru_cache(maxsize=128)
def _get_cached_type_hints(cls: type) -> dict[str, Any]:
    try:
        module = modules.get(cls.__module__)
        globalns = module.__dict__ if module else None
        return get_type_hints(cls, globalns=globalns)
    except Exception:
        return {}


def to_dict(obj: Any, _depth: int = 0) -> Any:
    """
    Converts any object to a JSON-serializable dictionary/list/scalar.
    Uses orjson round-trip to ensure consistency between signing and verification.
    """
    if _depth > 100:
        raise RecursionError("Maximum recursion depth (100) exceeded in to_dict")

    if obj is None:
        return None

    def default_handler(o: Any) -> Any:
        if hasattr(o, "_asdict"):
            return {k: v for k, v in o._asdict().items() if v is not None}
        if hasattr(o, "model_dump") and callable(o.model_dump):
            return {k: v for k, v in o.model_dump().items() if v is not None}
        if hasattr(o, "dict") and callable(o.dict):
            return {k: v for k, v in o.dict().items() if v is not None}
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, (UUID, datetime)):
            return str(o)
        if hasattr(o, "__dataclass_fields__"):
            return {f.name: getattr(o, f.name) for f in fields(o) if getattr(o, f.name) is not None}
        return str(o)

    try:
        # Round-trip through JSON ensures stable sorting and normalization for signing
        json_bytes = dumps(obj, default=default_handler, option=OPT_SORT_KEYS | OPT_NON_STR_KEYS)
    except TypeError as e:
        if "Recursion limit reached" in str(e):
            raise RecursionError("Maximum recursion depth (100) exceeded in to_dict") from e
        raise e
    normalized = loads(json_bytes)

    return _finalize_structure(normalized, _depth)


def _finalize_structure(data: Any, _depth: int = 0) -> Any:
    """Recursively removes None values and normalizes floats to ints."""
    if _depth > 100:
        raise RecursionError("Maximum recursion depth (100) exceeded in to_dict")
    if isinstance(data, dict):
        return {str(k): _finalize_structure(v, _depth + 1) for k, v in data.items() if v is not None}
    if isinstance(data, list):
        return [_finalize_structure(i, _depth + 1) for i in data]
    if isinstance(data, float) and data.is_integer():
        return int(data)
    return data


def from_dict(cls: type, data: Any) -> Any:
    """Deeply restores Models from dictionaries using type hints."""
    if data is None or isinstance(data, cls) or not isinstance(data, dict):
        return data

    type_hints = _get_cached_type_hints(cls)

    processed_data = {}
    if hasattr(cls, "_fields"):
        field_names = cls._fields
    elif is_dataclass(cls):
        field_names = [f.name for f in fields(cls)]
    else:
        return data

    for field_name in field_names:
        if field_name in data:
            val = data[field_name]
            field_type = type_hints.get(field_name, Any)
            processed_data[field_name] = _restore_field(field_type, val)

    try:
        return cls(**processed_data)
    except TypeError as e:
        raise ValueError(f"Failed to instantiate {cls.__name__}: {e}") from e


def _restore_field(field_type: Any, val: Any) -> Any:
    if val is None:
        return None

    origin = get_origin(field_type)
    args = get_args(field_type)

    if origin is Union or isinstance(field_type, UnionType):
        real_types = [a for a in args if a is not type(None)]
        for t in real_types:
            try:
                return _restore_field(t, val)
            except (ValueError, TypeError):
                continue
        return val

    if origin in (list, tuple) and args and isinstance(val, (list, tuple)):
        item_type = args[0]
        items = [_restore_field(item_type, i) for i in val]
        return tuple(items) if origin is tuple else items

    if origin is dict and len(args) > 1 and isinstance(val, dict):
        key_type = args[0]
        val_type = args[1]
        return {_restore_field(key_type, k): _restore_field(val_type, v) for k, v in val.items()}

    if (hasattr(field_type, "_fields") or is_dataclass(field_type)) and isinstance(val, dict):
        return from_dict(field_type, val)

    if isinstance(field_type, type) and issubclass(field_type, Enum):
        try:
            return field_type(val)
        except ValueError:
            return val

    if field_type is UUID and isinstance(val, str):
        try:
            return UUID(val)
        except ValueError:
            return val

    if field_type is datetime and isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return val

    return val


def json_dumps(obj: Any) -> str:
    """Wrapper for orjson.dumps returning str."""
    return dumps(to_dict(obj)).decode("utf-8")


def calculate_dict_hash(obj: Any) -> str:
    """Generates a stable SHA256 hash of an object."""
    message = dumps(to_dict(obj), option=OPT_SORT_KEYS)
    h: str = sha256(message).hexdigest()
    return h
