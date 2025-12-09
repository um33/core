"""Tests for shopping list Todo metadata mapping (store/quantity via description)."""

from __future__ import annotations

import pytest

from homeassistant.components.shopping_list.todo import (
    ShoppingTodoListEntity,
    _format_meta_description,
    _parse_meta_description,
)
from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntityFeature,
)

pytestmark = pytest.mark.asyncio


def test_parse_meta_description_store_and_quantity() -> None:
    """Test parsing store and quantity from description."""
    has_store, has_qty, store, qty = _parse_meta_description("Store: IKEA\nQuantity: 2")
    assert has_store is True
    assert has_qty is True
    assert store == "IKEA"
    assert qty == 2.0


def test_parse_meta_description_allows_clear_store() -> None:
    """Test parsing with empty store field clears the store value."""
    has_store, has_qty, store, qty = _parse_meta_description("Store:\nQuantity: 2")
    assert has_store is True
    assert store is None
    assert has_qty is True
    assert qty == 2.0


def test_parse_meta_description_ignores_invalid_qty() -> None:
    """Test parsing ignores invalid quantity values."""
    has_store, has_qty, store, qty = _parse_meta_description(
        "Store: Ica\nQuantity: nope"
    )
    assert has_store is True
    assert store == "Ica"
    # has_qty may be True but qty stays None; your code won’t update quantity in that case
    assert has_qty is True
    assert qty is None


def test_format_meta_description_hides_default_quantity_when_no_store() -> None:
    """Test format hides default quantity when no store is present."""
    # default qty is hidden if no store and qty == default
    assert _format_meta_description(None, 1.0) in (None, "")


def test_format_meta_description_includes_quantity_when_store_present() -> None:
    """Test format includes quantity when store is present."""
    desc = _format_meta_description("Biltema", 1.0)
    assert desc is not None
    assert "Store: Biltema" in desc
    assert "Quantity: 1" in desc


def test_supported_features_includes_description() -> None:
    """Test that entity supports setting description on items."""
    entity = ShoppingTodoListEntity(data=None, unique_id="x")  # type: ignore[arg-type]
    assert entity.supported_features & TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM


async def test_create_maps_description_to_store_and_quantity() -> None:
    """Test creating todo item maps description to store and quantity."""
    called = {}

    class StubData:
        async def async_add(
            self, name, store=None, quantity=None, complete=False, **kwargs
        ):
            called["name"] = name
            called["store"] = store
            called["quantity"] = quantity
            called["complete"] = complete

    entity = ShoppingTodoListEntity(data=StubData(), unique_id="x")

    item = TodoItem(
        summary="Milk",
        uid="1",
        status=TodoItemStatus.NEEDS_ACTION,
        description="Store: IKEA\nQuantity: 2",
    )
    await entity.async_create_todo_item(item)

    assert called["name"] == "Milk"
    assert called["store"] == "IKEA"
    assert called["quantity"] == 2.0
    assert called["complete"] is False


async def test_update_only_quantity_does_not_overwrite_store() -> None:
    """Test updating quantity does not overwrite existing store value."""
    updates = []

    class StubData:
        async def async_update(self, uid, data, **kwargs):
            updates.append((uid, data))

    entity = ShoppingTodoListEntity(data=StubData(), unique_id="x")

    item = TodoItem(
        summary="Milk",
        uid="abc",
        status=TodoItemStatus.COMPLETED,
        description="Quantity: 3",
    )
    await entity.async_update_todo_item(item)

    uid, data = updates[0]
    assert uid == "abc"
    assert data["name"] == "Milk"
    assert data["complete"] is True
    assert "store" not in data
    assert data["quantity"] == 3.0
