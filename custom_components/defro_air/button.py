"""Przyciski centrali Defro Air."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import DefroAirConfigEntry
from .entity import DefroAirEntity, DefroAirEntityDescription

PARALLEL_UPDATES = 1

SYNC_CLOCK = DefroAirEntityDescription(
    key="sync_clock", entity_category=EntityCategory.CONFIG
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DefroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([DefroAirSyncClockButton(entry.runtime_data, SYNC_CLOCK)])


class DefroAirSyncClockButton(DefroAirEntity, ButtonEntity):
    """Ustawia zegar sterownika na bieżący czas lokalny Home Assistanta."""

    async def async_press(self) -> None:
        now = dt_util.now().replace(tzinfo=None)
        await self._async_write(self.device.async_set_clock(now))
