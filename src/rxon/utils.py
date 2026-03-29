# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import fields, is_dataclass
from enum import Enum
from functools import lru_cache
from hashlib import sha256
from sys import modules
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints
from uuid import UUID

from orjson import OPT_SORT_KEYS, dumps, loads

__all__ = [
    "to_dict",
    "from_dict",
    "json_dumps",
    "loads",
    "calculate_dict_hash",
]


@lru_cache(maxsize=128)
def _get_cached_type_hints(cls: type) -> dict[str, Any]:
    """Caches type hints for a class to avoid expensive reflection on every call."""
    try:
        module = modules.get(cls.__module__)
        globalns = module.__dict__ if module else None
        return get_type_hints(cls, globalns=globalns)
    except Exception:
        return {}


def to_dict(obj: Any) -> Any:
    """Recursively converts Models, Enums and UUIDs to dicts for JSON serialization."""
    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, UUID):
        return str(obj)

    if hasattr(obj, "_asdict"):
        return {k: to_dict(v) for k, v in obj._asdict().items()}

    if hasattr(obj, "__dataclass_fields__"):
        return {f.name: to_dict(getattr(obj, f.name)) for f in fields(obj)}

    if isinstance(obj, (list, tuple)):
        return [to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


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
    """Helper to recursively restore a single field based on its type hint."""
    if val is None:
        return None

    origin = get_origin(field_type)
    args = get_args(field_type)

    if origin is Union or isinstance(field_type, UnionType):
        real_types = [a for a in args if a is not type(None)]
        if real_types:
            return _restore_field(real_types[0], val)
        return val

    if origin in (list, tuple) and args and isinstance(val, (list, tuple)):
        item_type = args[0]
        items = [_restore_field(item_type, i) for i in val]
        return tuple(items) if origin is tuple else items

    if origin is dict and len(args) > 1 and isinstance(val, dict):
        val_type = args[1]
        return {k: _restore_field(val_type, v) for k, v in val.items()}

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

    return val


def json_dumps(obj: Any) -> str:
    """Wrapper for orjson.dumps returning str."""
    return dumps(to_dict(obj)).decode("utf-8")


def calculate_dict_hash(obj: Any) -> str:
    """Generates a stable SHA256 hash of an object."""
    return sha256(dumps(to_dict(obj), option=OPT_SORT_KEYS)).hexdigest()
