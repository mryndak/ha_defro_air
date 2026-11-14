"""Wentylacja jako encja fan: bieg zadany 0–3 (rejestr 157).

Rejestr 157 istnieje tylko w nowszych wersjach programu sterownika, więc na
module MBP 1.1.4 ta encja nie powstaje.
"""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .coordinator import DefroAirConfigEntry
from .device import EXTENDED, MAX_GEAR
from .entity import DefroAirEntity, DefroAirEntityDescription, served

PARALLEL_UPDATES = 1

GEAR_RANGE = (1, MAX_GEAR)
DEFAULT_GEAR = 1

VENTILATION = DefroAirEntityDescription(key="ventilation", component=EXTENDED)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DefroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DefroAirFan(coordinator, description)
        for description in served(coordinator, (VENTILATION,))
    )


class DefroAirFan(DefroAirEntity, FanEntity):
    """Bieg zadany centrali."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = MAX_GEAR

    @property
    def _gear(self) -> int | None:
        return self.device.extended.target_gear

    @property
    def is_on(self) -> bool | None:
        gear = self._gear
        return None if gear is None else gear > 0

    @property
    def percentage(self) -> int | None:
        gear = self._gear
        if gear is None:
            return None
        if gear <= 0:
            return 0
        return ranged_value_to_percentage(GEAR_RANGE, min(gear, MAX_GEAR))

    async def _async_set_gear(self, gear: int) -> None:
        await self._async_write(self.device.extended.write("target_gear", gear))

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage <= 0:
            await self._async_set_gear(0)
            return
        await self._async_set_gear(
            math.ceil(percentage_to_ranged_value(GEAR_RANGE, percentage))
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_set_gear(DEFAULT_GEAR)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_gear(0)
