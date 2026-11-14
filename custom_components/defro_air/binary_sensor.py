"""Sensory binarne centrali Defro Air."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DefroAirConfigEntry
from .device import DefroAir
from .entity import DefroAirEntity, DefroAirEntityDescription, served

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DefroAirBinarySensorDescription(
    BinarySensorEntityDescription, DefroAirEntityDescription
):
    """Opis sensora binarnego."""

    value_fn: Callable[[DefroAir], bool | None]


def _state(key: str, **kwargs) -> DefroAirBinarySensorDescription:
    return DefroAirBinarySensorDescription(
        key=key, value_fn=lambda device: getattr(device.core, key), **kwargs
    )


BINARY_SENSORS: tuple[DefroAirBinarySensorDescription, ...] = (
    DefroAirBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.has_error,
    ),
    _state("bypass_active", device_class=BinarySensorDeviceClass.OPENING),
    _state("antifreeze_active", device_class=BinarySensorDeviceClass.RUNNING),
    _state("holiday_active"),
    _state("secondary_heating_active", device_class=BinarySensorDeviceClass.HEAT),
    _state("gwc_active", entity_registry_enabled_default=False),
    _state("digital_input_gear_3", entity_registry_enabled_default=False),
    _state("digital_input_hood", entity_registry_enabled_default=False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DefroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DefroAirBinarySensor(coordinator, description)
        for description in served(coordinator, BINARY_SENSORS)
    )


class DefroAirBinarySensor(DefroAirEntity, BinarySensorEntity):
    """Stan dwuwartościowy odczytywany z centrali."""

    entity_description: DefroAirBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.device)
