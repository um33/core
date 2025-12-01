"""A shopping list todo platform."""

import re
from typing import Any, cast

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NoMatchingShoppingListItem, ShoppingData
from .const import ATTR_QUANTITY, ATTR_STORE, DEFAULT_QUANTITY, DOMAIN

_STORE_RE = re.compile(r"^\s*store\s*[:=]\s*(.*)\s*$", re.IGNORECASE)
_QTY_RE = re.compile(r"^\s*quantity\s*[:=]\s*(.*)\s*$", re.IGNORECASE)


def _format_meta_description(store: str | None, quantity: float | None) -> str | None:
    lines: list[str] = []
    if store:
        lines.append(f"Store: {store}")
    if quantity is not None:
        # Only show if not default OR if store exists (so user sees both)
        if store or quantity != DEFAULT_QUANTITY:
            # avoid "2.0" when integer
            q_str = (
                str(int(quantity)) if float(quantity).is_integer() else str(quantity)
            )
            lines.append(f"Quantity: {q_str}")
    return "\n".join(lines) if lines else None


def _parse_meta_description(
    desc: str | None,
) -> tuple[bool, bool, str | None, float | None]:
    if not desc:
        return False, False, None, None
    has_store = False
    has_qty = False
    store: str | None = None
    qty: float | None = None

    for line in desc.splitlines():
        m = _STORE_RE.match(line)
        if m:
            has_store = True
            val = m.group(1).strip()
            store = val or None
            continue
        m = _QTY_RE.match(line)
        if m:
            has_qty = True
            raw = m.group(1).strip()
            if raw:
                try:
                    q = float(raw)
                    if q > 0:
                        qty = q
                except ValueError:
                    pass
            else:
                qty = float(DEFAULT_QUANTITY)

    return has_store, has_qty, store, qty


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the shopping_list todo platform."""
    shopping_data = hass.data[DOMAIN]
    entity = ShoppingTodoListEntity(shopping_data, unique_id=config_entry.entry_id)
    async_add_entities([entity], True)


class ShoppingTodoListEntity(TodoListEntity):
    """A To-do List representation of the Shopping List."""

    _attr_has_entity_name = True
    _attr_translation_key = "shopping_list"
    _attr_should_poll = False
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
    )

    def __init__(self, data: ShoppingData, unique_id: str) -> None:
        """Initialize ShoppingTodoListEntity."""
        self._attr_unique_id = unique_id
        self._data = data

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an item to the To-do list."""
        has_store, has_qty, store, qty = _parse_meta_description(item.description)

        store_val: str | None = store if has_store else None
        quantity_val: float = (
            qty if (has_qty and qty is not None) else float(DEFAULT_QUANTITY)
        )

        await self._data.async_add(
            item.summary or "",
            store=store_val,
            quantity=quantity_val,
            complete=(item.status == TodoItemStatus.COMPLETED),
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item to the To-do list."""
        data: dict[str, Any] = {
            "name": item.summary,
            "complete": item.status == TodoItemStatus.COMPLETED,
        }

        has_store, has_qty, store, qty = _parse_meta_description(item.description)
        if has_store:
            data[ATTR_STORE] = store  # can be None to clear
        if has_qty and qty is not None:
            data[ATTR_QUANTITY] = qty
        try:
            await self._data.async_update(item.uid, data)
        except NoMatchingShoppingListItem as err:
            raise HomeAssistantError(
                f"Shopping list item '{item.uid}' was not found"
            ) from err

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Add an item to the To-do list."""
        await self._data.async_remove_items(set(uids))

    async def async_move_todo_item(
        self, uid: str, previous_uid: str | None = None
    ) -> None:
        """Re-order an item to the To-do list."""

        try:
            await self._data.async_move_item(uid, previous_uid)
        except NoMatchingShoppingListItem as err:
            raise HomeAssistantError(
                f"Shopping list item '{uid}' could not be re-ordered"
            ) from err

    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        # Shopping list integration doesn't currently support config entry unload
        # so this code may not be used in practice, however it is here in case
        # this changes in the future.
        self.async_on_remove(self._data.async_add_listener(self.async_write_ha_state))

    @property
    def todo_items(self) -> list[TodoItem]:
        """Get items in the To-do list."""
        results = []
        for item in self._data.items:
            complete = cast(bool, item["complete"])
            status = (
                TodoItemStatus.COMPLETED if complete else TodoItemStatus.NEEDS_ACTION
            )

            store = cast(str | None, item.get("store"))
            qty_raw = item.get("quantity", DEFAULT_QUANTITY)
            try:
                qty = float(cast(float, qty_raw))
            except (ValueError, TypeError):
                qty = float(DEFAULT_QUANTITY)

            results.append(
                TodoItem(
                    summary=cast(str, item["name"]),
                    uid=cast(str, item["id"]),
                    status=status,
                    description=_format_meta_description(store, qty),
                )
            )
        return results
