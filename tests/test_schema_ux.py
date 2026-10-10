# Copyright (c) 2025-2026 Dmitrii Gagarin aka madgagarin
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Annotated, Any

from msgspec import Struct

from rxon.schema import (
    Header,
    extract_input_schema_from_func,
    extract_json_schema,
    extract_output_schema_from_func,
    extract_skill_contract,
    validate_data,
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


def test_header_marker_properties() -> None:
    h = Header("X-Trace-Id", default="none")
    assert h.name == "X-Trace-Id"
    assert h.default == "none"
    assert h.is_header is True
    assert repr(h) == "Header('X-Trace-Id')"


def test_extract_json_schema_pydantic() -> None:
    schema = extract_json_schema(PydanticUser)
    assert schema is not None
    assert schema["type"] == "object"
    assert "user_id" in schema["properties"]
    assert "email" in schema["properties"]
    assert "user_id" in schema["required"]
    assert "email" in schema["required"]


def test_extract_json_schema_dataclass() -> None:
    schema = extract_json_schema(DataclassItem)
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["properties"]["item_id"]["type"] == "integer"
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["required"] == ["item_id", "name"]


def test_single_model_signature_returns_flat_schema() -> None:
    async def start_handler(order: MsgspecOrder, ctx: Any, actions: Any) -> None:
        pass

    schema = extract_input_schema_from_func(start_handler)
    assert schema is not None
    assert schema["type"] == "object"
    assert "order_id" in schema["properties"]
    assert "amount" in schema["properties"]
    assert "order" not in schema["properties"]


def test_single_pydantic_model_flat_schema() -> None:
    def init(user: PydanticUser, context: Any = None) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert "user_id" in schema["properties"]
    assert "user" not in schema["properties"]


def test_composite_schema_multiple_models() -> None:
    async def init(user: PydanticUser, order: MsgspecOrder, ctx: Any) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert schema["type"] == "object"
    assert "user" in schema["properties"]
    assert "order" in schema["properties"]
    assert schema["properties"]["user"]["type"] == "object"
    assert schema["properties"]["order"]["type"] == "object"
    assert set(schema["required"]) == {"user", "order"}


def test_composite_schema_model_and_scalar() -> None:
    async def init(order: MsgspecOrder, dry_run: bool = False, ctx: Any = None) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert "order" in schema["properties"]
    assert "dry_run" in schema["properties"]
    assert schema["properties"]["dry_run"]["type"] == "boolean"
    assert schema["required"] == ["order"]


def test_scalar_only_signature() -> None:
    def init(user_id: str, count: int = 1) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["properties"]["user_id"]["type"] == "string"
    assert schema["properties"]["count"]["type"] == "integer"
    assert schema["required"] == ["user_id"]


def test_ignores_header_annotations() -> None:
    async def init(
        order: MsgspecOrder,
        ctx: Any,
        correlation_id: Annotated[str | None, Header("X-Correlation-ID")] = None,
    ) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert "order_id" in schema["properties"]
    assert "correlation_id" not in schema["properties"]


def test_no_business_parameters_returns_none() -> None:
    async def init(ctx: Any, task_files: Any) -> None:
        pass

    assert extract_input_schema_from_func(init) is None


def test_extract_output_schema_from_func() -> None:
    async def terminal_step(ctx: Any) -> OrderReceipt:
        return OrderReceipt(receipt_id="r1", paid=True)

    schema = extract_output_schema_from_func(terminal_step)
    assert schema is not None
    assert schema["type"] == "object"
    assert "receipt_id" in schema["properties"]

    async def none_step(ctx: Any) -> None:
        pass

    assert extract_output_schema_from_func(none_step) is None

    async def dict_step(ctx: Any) -> dict[str, Any]:
        return {}

    assert extract_output_schema_from_func(dict_step) is None


def test_extract_skill_contract_with_modern_blueprint() -> None:
    class MockBlueprint:
        start_state = "init"
        end_states = ["finish"]
        handlers: dict[str, Any] = {}

    async def mock_init(order: MsgspecOrder, ctx: Any) -> None:
        pass

    async def mock_finish(ctx: Any) -> OrderReceipt:
        return OrderReceipt(receipt_id="r-ok", paid=True)

    MockBlueprint.handlers = {
        "init": mock_init,
        "finish": mock_finish,
    }

    contract = extract_skill_contract(MockBlueprint)
    assert contract["input_schema"] is not None
    assert "order_id" in contract["input_schema"]["properties"]
    assert contract["output_schema"] is not None
    assert "receipt_id" in contract["output_schema"]["properties"]


def test_validation_works_with_inferred_schema() -> None:
    async def init(order: MsgspecOrder) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    is_valid, err = validate_data({"order_id": 100, "amount": 25.5}, schema)
    assert is_valid is True
    assert err is None

    is_valid, err = validate_data({"order_id": "not_an_int"}, schema)
    assert is_valid is False
    assert err is not None


def test_validation_negative_non_dict_payload() -> None:
    schema = extract_json_schema(PydanticUser)
    is_valid, err = validate_data(None, schema)
    assert is_valid is False
    assert err is not None
    assert "null" in err.lower() or "expected" in err.lower()

    is_valid, err = validate_data("hello", schema)
    assert is_valid is False

    is_valid, err = validate_data([1, 2, 3], schema)
    assert is_valid is False


def test_composite_schema_validation_negative() -> None:
    async def init(user: PydanticUser, order: MsgspecOrder) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None

    is_valid, err = validate_data({"order": {"order_id": 1, "amount": 10.0}}, schema)
    assert is_valid is False
    assert err is not None
    assert "user" in err

    is_valid, err = validate_data(
        {"user": {"user_id": 12345, "email": "a@b.com"}, "order": {"order_id": 1, "amount": 10.0}},
        schema,
    )
    assert is_valid is False
    assert err is not None
    assert "user_id" in err or "user" in err

    is_valid, err = validate_data(
        {
            "user": {"user_id": "u1", "email": "a@b.com"},
            "order": {"order_id": 1, "amount": 10.0},
            "unauthorized_field": "hacked",
        },
        schema,
    )
    assert is_valid is False
    assert err is not None
    assert "unauthorized_field" in err


def test_extract_schema_invalid_callables_and_edge_types() -> None:
    assert extract_input_schema_from_func(None) is None
    assert extract_input_schema_from_func("not_a_func") is None
    assert extract_output_schema_from_func(None) is None
    assert extract_output_schema_from_func(42) is None

    def anon(x: Any, y: Any) -> Any:
        return x + y

    schema = extract_input_schema_from_func(anon)
    assert schema is not None
    assert "x" in schema["properties"]
    assert "y" in schema["properties"]
    assert set(schema["required"]) == {"x", "y"}


def test_signature_with_varargs_kwargs_and_self() -> None:
    class Service:
        def process(self, order: MsgspecOrder, *args: Any, **kwargs: Any) -> None:
            pass

    schema = extract_input_schema_from_func(Service.process)
    assert schema is not None
    assert "order_id" in schema["properties"]
    assert "self" not in schema["properties"]
    assert "args" not in schema["properties"]
    assert "kwargs" not in schema["properties"]


def test_signature_with_optional_defaults() -> None:
    def init(user: PydanticUser, dry_run: bool = True, tag: str | None = None) -> None:
        pass

    schema = extract_input_schema_from_func(init)
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["required"] == ["user"]
    assert "dry_run" in schema["properties"]
    assert "tag" in schema["properties"]


def test_deeply_nested_pydantic_model_schema() -> None:
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

    valid, err = validate_data({"cart_id": "c1", "items": [{"sku": "SKU-1", "qty": 2}]}, schema)
    assert valid is True
    assert err is None

    valid, err = validate_data({"cart_id": "c1", "items": [{"sku": "SKU-1", "qty": "not_an_int"}]}, schema)
    assert valid is False
    assert err is not None


def test_untyped_input_variations() -> None:
    def handler_dict(input: dict) -> None:  # type: ignore[type-arg]
        pass

    assert extract_input_schema_from_func(handler_dict) is None

    def handler_any(input: Any) -> None:
        pass

    assert extract_input_schema_from_func(handler_any) is None

    def handler_generic_dict(input: dict[str, Any]) -> None:
        pass

    assert extract_input_schema_from_func(handler_generic_dict) is None

    def handler_unannotated(input) -> None:  # type: ignore[no-untyped-def]
        pass

    assert extract_input_schema_from_func(handler_unannotated) is None


def test_string_literal_type_annotations() -> None:
    assert extract_json_schema("str") == {"type": "string"}
    assert extract_json_schema("int") == {"type": "integer"}
    assert extract_json_schema("float") == {"type": "number"}
    assert extract_json_schema("bool") == {"type": "boolean"}

    def handler_strings(x: "int", y: "str", z: "bool", w: "float") -> None:
        pass

    schema = extract_input_schema_from_func(handler_strings)
    assert schema is not None
    assert schema["properties"]["x"] == {"type": "integer"}
    assert schema["properties"]["y"] == {"type": "string"}
    assert schema["properties"]["z"] == {"type": "boolean"}
    assert schema["properties"]["w"] == {"type": "number"}


def test_dataclass_optional_fields_not_in_required() -> None:
    @dataclass
    class Settings:
        title: str
        subtitle: str | None = None
        limit: int = 10

    schema = extract_json_schema(Settings)
    assert schema is not None
    assert schema["type"] == "object"
    assert schema["required"] == ["title"]
    assert "subtitle" in schema["properties"]
    assert "limit" in schema["properties"]
