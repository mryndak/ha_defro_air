"""Sensory centrali Defro Air."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import DefroAirConfigEntry
from .device import EXTENDED, DefroAir
from .entity import DefroAirEntity, DefroAirEntityDescription, served

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DefroAirSensorDescription(SensorEntityDescription, DefroAirEntityDescription):
    value_fn: Callable[[DefroAir], Any]
    attributes_fn: Callable[[DefroAir], dict[str, Any]] | None = None


def _clock(device: DefroAir) -> datetime | None:
    """Zegar sterownika jako czas w strefie Home Assistanta."""
    clock = device.clock
    if clock is None:
        return None
    return clock.replace(tzinfo=dt_util.get_default_time_zone())


def _temperature(key: str, *, enabled: bool = True) -> DefroAirSensorDescription:
    return DefroAirSensorDescription(
        key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
        value_fn=lambda device: getattr(device, key),
    )


def _flow(key: str) -> DefroAirSensorDescription:
    return DefroAirSensorDescription(
        key=key,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: getattr(device.core, key),
    )


SENSORS: tuple[DefroAirSensorDescription, ...] = (
    _flow("supply_flow"),
    _flow("extract_flow"),
    DefroAirSensorDescription(
        key="supply_gear",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.core.supply_gear,
    ),
    DefroAirSensorDescription(
        key="extract_gear",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.core.extract_gear,
    ),
    _temperature("outdoor_temperature"),
    _temperature("extract_temperature"),
    _temperature("supply_temperature"),
    _temperature("exhaust_temperature"),
    _temperature("heater_control_temperature"),
    # Czujniki opcjonalne: w wielu centralach nie są podłączone.
    _temperature("gwc_temperature", enabled=False),
    _temperature("secondary_heating_temperature", enabled=False),
    DefroAirSensorDescription(
        key="efficiency",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.efficiency,
    ),
    DefroAirSensorDescription(
        key="recovered_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.recovered_power,
    ),
    DefroAirSensorDescription(
        key="filter_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.core.filter_days,
    ),
    DefroAirSensorDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: (
            None if device.core.errors is None else int(device.core.errors)
        ),
        attributes_fn=lambda device: {"errors": device.error_keys},
    ),
    DefroAirSensorDescription(
        key="clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_clock,
    ),
    DefroAirSensorDescription(
        key="filter_runtime",
        component=EXTENDED,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.extended.filter_runtime,
    ),
    DefroAirSensorDescription(
        key="unit_size",
        component=EXTENDED,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.extended.unit_size,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DefroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        DefroAirSensor(coordinator, description)
        for description in served(coordinator, SENSORS)
    )


class DefroAirSensor(DefroAirEntity, SensorEntity):
    entity_description: DefroAirSensorDescription

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.device)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.device)
