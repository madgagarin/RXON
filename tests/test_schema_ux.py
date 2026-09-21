# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Annotated, Any

from msgspec import Struct
from pydantic import BaseModel

from rxon.schema import (
    extract_input_schema_from_func,
    extract_json_schema,
    extract_output_schema_from_func,
    extract_skill_contract,
    validate_data,
)


class DummyHeader:
    def __init__(self, name: str):
        self.name = name
        self.is_header = True


def Header(name: str):
    return DummyHeader(name)


class MsgspecOrder(Struct):
    order_id: int
    amount: float
    currency: str = "USD"


class PydanticUser(BaseModel):
    user_id: str
    email: str
    is_active: bool = True


@dataclass
class DataclassItem:
    item_id: int
    name: str


class OrderReceipt(BaseModel):
    receipt_id: str
    paid: bool


def test_extract_json_schema_pydantic():
    schema = extract_json_schema(PydanticUser)
    assert schema is not None
    assert schema["type"] == "object"
    assert "user_id" in schema["properties"]
    assert "email" in schema["properties"]
    assert "user_id" in schema["required"]
    assert "email" in schema["required"]


def test_extract_json_schema_dataclass():
    schema = extract_json_schema(DataclassItem)
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["properties"]["item_id"]["type"] == "integer"
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["required"] == ["item_id", "name"]


def test_single_model_signature_returns_flat_schema():
    async def start_handler(order: MsgspecOrder, ctx: Any, actions: Any):
        pass

    schema = extract_input_schema_from_func(start_handler)
    assert schema is not None
    assert schema["type"] == "object"
    assert "order_id" in schema["properties"]
    assert "amount" in schema["properties"]
    assert "order" not in schema["properties"]  # Flat schema!


def test_single_pydantic_model_flat_schema():
    def init(user: PydanticUser, context: Any = None):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert "user_id" in schema["properties"]
    assert "user" not in schema["properties"]


def test_composite_schema_multiple_models():
    async def init(user: PydanticUser, order: MsgspecOrder, ctx: Any):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert schema["type"] == "object"
    assert "user" in schema["properties"]
    assert "order" in schema["properties"]
    assert schema["properties"]["user"]["type"] == "object"
    assert schema["properties"]["order"]["type"] == "object"
    assert set(schema["required"]) == {"user", "order"}


def test_composite_schema_model_and_scalar():
    async def init(order: MsgspecOrder, dry_run: bool = False, ctx: Any = None):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert "order" in schema["properties"]
    assert "dry_run" in schema["properties"]
    assert schema["properties"]["dry_run"]["type"] == "boolean"
    assert schema["required"] == ["order"]  # dry_run has default


def test_scalar_only_signature():
    def init(user_id: str, count: int = 1):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["properties"]["user_id"]["type"] == "string"
    assert schema["properties"]["count"]["type"] == "integer"
    assert schema["required"] == ["user_id"]


def test_ignores_header_annotations():
    async def init(
        order: MsgspecOrder,
        ctx: Any,
        correlation_id: Annotated[str | None, Header("X-Correlation-ID")] = None,
    ):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    # Because correlation_id has Header annotation, only order remains -> flat schema!
    assert "order_id" in schema["properties"]
    assert "correlation_id" not in schema["properties"]


def test_no_business_parameters_returns_none():
    async def init(ctx: Any, task_files: Any):
        pass

    assert extract_input_schema_from_func(init) is None


def test_extract_output_schema_from_func():
    async def terminal_step(ctx: Any) -> OrderReceipt:
        pass

    schema = extract_output_schema_from_func(terminal_step)
    assert schema is not None
    assert schema["type"] == "object"
    assert "receipt_id" in schema["properties"]

    async def none_step(ctx: Any) -> None:
        pass

    assert extract_output_schema_from_func(none_step) is None

    async def dict_step(ctx: Any) -> dict[str, Any]:
        pass

    assert extract_output_schema_from_func(dict_step) is None


def test_extract_skill_contract_with_modern_blueprint():
    class MockBlueprint:
        start_state = "init"
        end_states = ["finish"]
        handlers = {
            "init": lambda order: None,
            "finish": lambda ctx: None,
        }

    # Add type hints to mock handlers
    async def mock_init(order: MsgspecOrder, ctx: Any):
        pass

    async def mock_finish(ctx: Any) -> OrderReceipt:
        pass

    MockBlueprint.handlers["init"] = mock_init
    MockBlueprint.handlers["finish"] = mock_finish

    contract = extract_skill_contract(MockBlueprint)
    assert contract["input_schema"] is not None
    assert "order_id" in contract["input_schema"]["properties"]
    assert contract["output_schema"] is not None
    assert "receipt_id" in contract["output_schema"]["properties"]


def test_validation_works_with_inferred_schema():
    async def init(order: MsgspecOrder):
        pass

    schema = extract_input_schema_from_func(init)
    is_valid, err = validate_data({"order_id": 100, "amount": 25.5}, schema)
    assert is_valid is True
    assert err is None

    is_valid, err = validate_data({"order_id": "not_an_int"}, schema)
    assert is_valid is False
    assert err is not None


# --- NEGATIVE & BOUNDARY CASES ---


def test_validation_negative_non_dict_payload():
    schema = extract_json_schema(PydanticUser)
    # 1. Null payload
    is_valid, err = validate_data(None, schema)
    assert is_valid is False
    assert "null" in err.lower() or "expected" in err.lower()

    # 2. String payload
    is_valid, err = validate_data("hello", schema)
    assert is_valid is False

    # 3. List payload
    is_valid, err = validate_data([1, 2, 3], schema)
    assert is_valid is False


def test_composite_schema_validation_negative():
    async def init(user: PydanticUser, order: MsgspecOrder):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None

    # Missing "user" key entirely
    is_valid, err = validate_data({"order": {"order_id": 1, "amount": 10.0}}, schema)
    assert is_valid is False
    assert "user" in err

    # Nested type violation inside "user" (user_id must be str, got int)
    is_valid, err = validate_data(
        {"user": {"user_id": 12345, "email": "a@b.com"}, "order": {"order_id": 1, "amount": 10.0}},
        schema,
    )
    assert is_valid is False
    assert "user_id" in err or "user" in err

    # Unexpected extra property in strict composite schema
    is_valid, err = validate_data(
        {
            "user": {"user_id": "u1", "email": "a@b.com"},
            "order": {"order_id": 1, "amount": 10.0},
            "unauthorized_field": "hacked",
        },
        schema,
    )
    assert is_valid is False
    assert "unauthorized_field" in err


def test_extract_schema_invalid_callables_and_edge_types():
    # 1. None or non-callable
    assert extract_input_schema_from_func(None) is None
    assert extract_input_schema_from_func("not_a_func") is None
    assert extract_output_schema_from_func(None) is None
    assert extract_output_schema_from_func(42) is None

    # 2. Lambda without annotations
    anon = lambda x, y: x + y  # noqa: E731
    schema = extract_input_schema_from_func(anon)
    assert schema is not None
    assert "x" in schema["properties"]
    assert "y" in schema["properties"]
    assert set(schema["required"]) == {"x", "y"}


def test_signature_with_varargs_kwargs_and_self():
    class Service:
        def process(self, order: MsgspecOrder, *args, **kwargs):
            pass

    schema = extract_input_schema_from_func(Service.process)
    assert schema is not None
    # self, *args, **kwargs are excluded -> flat schema for order!
    assert "order_id" in schema["properties"]
    assert "self" not in schema["properties"]
    assert "args" not in schema["properties"]
    assert "kwargs" not in schema["properties"]


def test_signature_with_optional_defaults():
    def init(user: PydanticUser, dry_run: bool = True, tag: str | None = None):
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert schema["type"] == "object"
    # user is required, dry_run and tag have defaults -> not in required
    assert schema["required"] == ["user"]
    assert "dry_run" in schema["properties"]
    assert "tag" in schema["properties"]


def test_deeply_nested_pydantic_model_schema():
    class Item(BaseModel):
        sku: str
        qty: int

    class Cart(BaseModel):
        cart_id: str
        items: list[Item]

    schema = extract_json_schema(Cart)
    assert schema is not None
    assert schema["type"] == "object"
    assert "cart_id" in schema["properties"]
    assert "items" in schema["properties"]
    assert schema["properties"]["items"]["type"] == "array"
    assert "$ref" in schema["properties"]["items"]["items"] or "properties" in schema["properties"]["items"]["items"]

    # Validate valid payload
    valid, err = validate_data({"cart_id": "c1", "items": [{"sku": "SKU-1", "qty": 2}]}, schema)
    assert valid is True
    assert err is None

    # Validate negative payload
    valid, err = validate_data({"cart_id": "c1", "items": [{"sku": "SKU-1", "qty": "not_an_int"}]}, schema)
    assert valid is False
    assert err is not None

