"""Nastawy liczbowe centrali Defro Air."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DefroAirConfigEntry
from .device import EXTENDED, MAX_FIREPLACE, MAX_HOLIDAY_DAYS, MAX_PARTY
from .entity import DefroAirEntity, DefroAirEntityDescription, served

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DefroAirNumberDescription(NumberEntityDescription, DefroAirEntityDescription):
    """Nastawa: pole rejestru o nazwie równej kluczowi encji."""


def _installer(key: str, low: int, high: int, unit: str, **kwargs):
    """Nastawa instalatora: ukryta domyślnie, bo zmienia charakterystykę centrali."""
    return DefroAirNumberDescription(
        key=key,
        component=EXTENDED,
        native_min_value=low,
        native_max_value=high,
        native_step=1,
        native_unit_of_measurement=unit,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        **kwargs,
    )


_FLOW = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR

NUMBERS: tuple[DefroAirNumberDescription, ...] = (
    DefroAirNumberDescription(
        key="holiday_days",
        native_min_value=0,
        native_max_value=MAX_HOLIDAY_DAYS,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.DAYS,
        mode=NumberMode.BOX,
    ),
    DefroAirNumberDescription(
        key="party",
        native_min_value=0,
        native_max_value=MAX_PARTY,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    DefroAirNumberDescription(
        key="fireplace",
        native_min_value=0,
        native_max_value=MAX_FIREPLACE,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        mode=NumberMode.BOX,
    ),
    _installer("gear_1_power", 1, 100, PERCENTAGE),
    _installer("gear_2_power", 1, 100, PERCENTAGE),
    _installer("gear_3_power", 1, 100, PERCENTAGE),
    _installer("gear_1_flow", 0, 1342, _FLOW),
    _installer("gear_2_flow", 0, 1342, _FLOW),
    _installer("gear_3_flow", 0, 1342, _FLOW),
    _installer(
        "bypass_low_temperature",
        10,
        30,
        UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
    _installer(
        "bypass_comfort_temperature",
        18,
        25,
        UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DefroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DefroAirNumber(coordinator, description)
        for description in served(coordinator, NUMBERS)
    )


class DefroAirNumber(DefroAirEntity, NumberEntity):
    """Nastawa zapisywana do rejestru centrali."""

    entity_description: DefroAirNumberDescription

    @property
    def _component(self):
        return getattr(self.device, self.entity_description.component)

    @property
    def native_value(self) -> float | None:
        return getattr(self._component, self.entity_description.key)

    async def async_set_native_value(self, value: float) -> None:
        await self._async_write(
            self._component.write(self.entity_description.key, int(value))
        )
