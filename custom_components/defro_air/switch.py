"""Przełączniki centrali Defro Air."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DefroAirConfigEntry
from .device import EXTENDED
from .entity import DefroAirEntity, DefroAirEntityDescription, served

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DefroAirSwitchDescription(SwitchEntityDescription, DefroAirEntityDescription):
    """Przełącznik: pole rejestru 0/1 o nazwie równej kluczowi encji."""


SWITCHES: tuple[DefroAirSwitchDescription, ...] = (
    DefroAirSwitchDescription(key="bypass_enabled"),
    DefroAirSwitchDescription(key="gwc_enabled", entity_registry_enabled_default=False),
    DefroAirSwitchDescription(key="weekly_enabled", component=EXTENDED),
    DefroAirSwitchDescription(key="windows_mode", component=EXTENDED),
    DefroAirSwitchDescription(
        key="humidifier_enabled",
        component=EXTENDED,
        entity_registry_enabled_default=False,
    ),
    DefroAirSwitchDescription(
        key="flow_balancing",
        component=EXTENDED,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DefroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DefroAirSwitch(coordinator, description)
        for description in served(coordinator, SWITCHES)
    )


class DefroAirSwitch(DefroAirEntity, SwitchEntity):
    """Przełącznik zapisujący 0 lub 1 do rejestru centrali."""

    entity_description: DefroAirSwitchDescription

    @property
    def _component(self):
        return getattr(self.device, self.entity_description.component)

    @property
    def is_on(self) -> bool | None:
        return getattr(self._component, self.entity_description.key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_write(
            self._component.write(self.entity_description.key, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_write(
            self._component.write(self.entity_description.key, False)
        )
