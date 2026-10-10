# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from msgspec import Struct

from rxon.schema import (
    _MAX_TYPE_SCHEMA_CACHE_SIZE,
    _type_schema_cache,
    extract_input_schema_from_func,
    extract_json_schema,
    extract_output_schema_from_func,
    extract_schema_from_func,
)


class BaseModel:
    """Lightweight duck-typed mock of Pydantic BaseModel for zero-dependency testing."""

    def __init__(self, **kwargs: Any):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        hints = getattr(cls, "__annotations__", {})

        for name, tp in hints.items():
            if name.startswith("_"):
                continue

            if hasattr(tp, "model_json_schema") and callable(tp.model_json_schema):
                properties[name] = tp.model_json_schema()
            elif getattr(tp, "__origin__", None) is list or tp is list:
                args = getattr(tp, "__args__", ())
                item_tp = args[0] if args else Any
                if hasattr(item_tp, "model_json_schema") and callable(item_tp.model_json_schema):
                    properties[name] = {"type": "array", "items": item_tp.model_json_schema()}
                elif item_tp is int:
                    properties[name] = {"type": "array", "items": {"type": "integer"}}
                else:
                    properties[name] = {"type": "array", "items": {"type": "string"}}
            elif tp is int:
                properties[name] = {"type": "integer"}
            elif tp is float:
                properties[name] = {"type": "number"}
            elif tp is bool:
                properties[name] = {"type": "boolean"}
            else:
                properties[name] = {"type": "string"}

            if not hasattr(cls, name):
                required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }


class UserProfile(BaseModel):
    user_id: int
    username: str
    tags: list[str] = []


@dataclass
class OrderItem:
    item_id: str
    quantity: int
    price: float


class InventoryRecord(Struct):
    sku: str
    stock: int


class SlottedCallable:
    """Callable with __slots__ and no __dict__ attribute."""

    __slots__ = ("multiplier",)

    def __init__(self, multiplier: int = 2):
        self.multiplier = multiplier

    def __call__(self, count: int) -> int:
        return count * self.multiplier


def test_positive_extract_json_schema_cache_hit() -> None:
    """Verify that extract_json_schema caches schemas for models and primitives."""
    schema1 = extract_json_schema(UserProfile)
    schema2 = extract_json_schema(UserProfile)
    assert schema1 is not None
    assert id(schema1) == id(schema2)
    assert schema1["type"] == "object"
    assert "user_id" in schema1["properties"]

    # Dataclass caching
    ds1 = extract_json_schema(OrderItem)
    ds2 = extract_json_schema(OrderItem)
    assert ds1 is not None
    assert id(ds1) == id(ds2)

    # Struct caching
    st1 = extract_json_schema(InventoryRecord)
    st2 = extract_json_schema(InventoryRecord)
    assert st1 is not None
    assert id(st1) == id(st2)


def test_positive_function_attribute_caching() -> None:
    """Verify that extract_input_schema_from_func and extract_output_schema_from_func attach caches."""

    def test_handler(user: UserProfile, factor: int = 1) -> OrderItem:
        return OrderItem(item_id=str(user.user_id), quantity=factor, price=10.0)

    in_schema1 = extract_input_schema_from_func(test_handler)
    assert hasattr(test_handler, "_rxon_input_schema")
    in_schema2 = extract_input_schema_from_func(test_handler)
    assert id(in_schema1) == id(in_schema2)

    out_schema1 = extract_output_schema_from_func(test_handler)
    assert hasattr(test_handler, "_rxon_output_schema")
    out_schema2 = extract_output_schema_from_func(test_handler)
    assert id(out_schema1) == id(out_schema2)


def test_positive_single_model_parameter_unwrap() -> None:
    """Single model parameter unwraps to the model's schema directly."""

    def single_arg_func(profile: UserProfile) -> None:
        pass

    schema = extract_input_schema_from_func(single_arg_func)
    assert schema is not None
    assert schema["type"] == "object"
    assert "user_id" in schema.get("properties", {})


def test_negative_extract_from_non_callables() -> None:
    """Verify safe handling of non-callable values."""
    assert extract_input_schema_from_func(None) is None
    assert extract_input_schema_from_func(42) is None
    assert extract_input_schema_from_func("not_a_func") is None
    assert extract_input_schema_from_func({}) is None

    assert extract_output_schema_from_func(None) is None
    assert extract_output_schema_from_func(123) is None
    assert extract_output_schema_from_func([]) is None


def test_negative_extract_schema_from_missing_arg() -> None:
    """Verify querying a non-existent parameter name returns None safely."""

    def dummy(x: int) -> None:
        pass

    assert extract_schema_from_func(dummy, "non_existent") is None
    assert extract_schema_from_func(None, "x") is None


def test_negative_unsupported_or_empty_types() -> None:
    """Primitive types or unknown types handled without exceptions."""
    schema = extract_json_schema(Any)
    assert schema == {} or isinstance(schema, dict)

    # Empty types / None type
    none_schema = extract_json_schema(type(None))
    assert none_schema == {"type": "null"}


def test_edge_case_slotted_callable_without_dict() -> None:
    """Slotted callables have no __dict__; extract_input_schema_from_func must not crash."""
    slotted_fn = SlottedCallable(3)
    assert not hasattr(slotted_fn, "__dict__")

    # Should compute input schema without throwing AttributeError
    schema = extract_input_schema_from_func(slotted_fn)
    assert schema is not None
    assert "count" in schema.get("properties", {})

    # Builtin functions like len have no __dict__
    len_schema = extract_input_schema_from_func(len)
    assert len_schema is None or isinstance(len_schema, dict)


def test_edge_case_builtin_function_output_schema() -> None:
    """Builtin functions like abs or id should return schema without crashing."""
    schema = extract_output_schema_from_func(abs)
    assert schema is None or isinstance(schema, dict)


def test_edge_case_lru_cache_fifo_eviction() -> None:
    """Verify that _type_schema_cache maintains bounded size <= _MAX_TYPE_SCHEMA_CACHE_SIZE (2048)."""
    overflow_count = 2100

    # Dynamically create unique classes to stress the cache
    for i in range(overflow_count):
        dynamic_cls = type(
            f"DynamicModel_{i}",
            (BaseModel,),
            {
                "__annotations__": {"val": int},
                "val": 0,
            },
        )
        extract_json_schema(dynamic_cls)

    assert len(_type_schema_cache) <= _MAX_TYPE_SCHEMA_CACHE_SIZE
    assert len(_type_schema_cache) == _MAX_TYPE_SCHEMA_CACHE_SIZE


def test_edge_case_multithreaded_cache_access() -> None:
    """Verify concurrent reads and writes to _type_schema_cache are thread-safe."""

    def worker(tid: int) -> bool:
        results = []
        for i in range(50):
            model_cls = type(
                f"ThreadModel_{tid}_{i}",
                (BaseModel,),
                {
                    "__annotations__": {"field": str},
                    "field": "test",
                },
            )
            sch1 = extract_json_schema(model_cls)
            sch2 = extract_json_schema(model_cls)
            results.append(id(sch1) == id(sch2))
        return all(results)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, t) for t in range(8)]
        assert all(f.result() for f in futures)
