from dataclasses import fields
from enum import Enum
from hashlib import sha256
from typing import Any

from orjson import OPT_SORT_KEYS, dumps

__all__ = [
    "to_dict",
    "json_dumps",
    "calculate_dict_hash",
]


def to_dict(obj: Any) -> Any:
    """
    Recursively converts NamedTuples, Dataclasses and Enums to dicts/values for JSON serialization.
    Handles dataclasses with slots and standard fields.
    """
    if isinstance(obj, Enum):
        return obj.value

    if hasattr(obj, "_asdict"):  # NamedTuple
        return {k: to_dict(v) for k, v in obj._asdict().items()}

    if hasattr(obj, "__dataclass_fields__"):  # Dataclass
        # For slots=True dataclasses, we iterate over fields
        return {f.name: to_dict(getattr(obj, f.name)) for f in fields(obj)}

    if isinstance(obj, list):
        return [to_dict(i) for i in obj]
    if isinstance(obj, tuple):
        return [to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def json_dumps(obj: Any) -> str:
    """
    Wrapper for orjson.dumps that returns str (required by aiohttp).
    Automatically converts NamedTuples to dicts.
    """
    return dumps(to_dict(obj)).decode("utf-8")


def calculate_dict_hash(obj: Any) -> str:
    """Generates a stable SHA256 hash of an object."""
    return sha256(dumps(to_dict(obj), option=OPT_SORT_KEYS)).hexdigest()
