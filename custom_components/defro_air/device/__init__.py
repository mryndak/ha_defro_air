"""Model rekuperatora Defro Air, niezależny od Home Assistanta."""

from __future__ import annotations

from datetime import datetime

from modbus_connection import ModbusUnit
from modbus_connection.model import Device, UpdateReport, read_optional

from .codec import (
    ErrorFlags,
    decode_clock,
    encode_date,
    encode_time,
    error_keys,
    heat_recovery_efficiency,
    plausible_temperature,
    recovered_power,
)
from .registers import (
    MAX_FIREPLACE,
    MAX_GEAR,
    MAX_HOLIDAY_DAYS,
    MAX_PARTY,
    Core,
    Extended,
)

__all__ = [
    "MAX_FIREPLACE",
    "MAX_GEAR",
    "MAX_HOLIDAY_DAYS",
    "MAX_PARTY",
    "Core",
    "DefroAir",
    "ErrorFlags",
    "Extended",
    "UpdateReport",
    "error_keys",
]

CORE = "core"
EXTENDED = "extended"


class DefroAir(Device):
    def __init__(self, unit: ModbusUnit) -> None:
        super().__init__(unit)
        self.core = Core(unit)
        self.extended: Extended | None = None

    async def _async_setup(self) -> None:
        self.extended = await read_optional(Extended(self.modbus_unit))

    @property
    def components(self) -> tuple[str, ...]:
        return (CORE, EXTENDED) if self.extended is not None else (CORE,)

    async def async_update(self) -> UpdateReport:
        return await self.async_poll((CORE, EXTENDED))

    async def async_read_all_raw(self) -> dict[str, dict[int, int | bool]]:
        return await self.async_read_raw((CORE, EXTENDED))

    @property
    def outdoor_temperature(self) -> float | None:
        return plausible_temperature(self.core.outdoor_temperature)

    @property
    def extract_temperature(self) -> float | None:
        return plausible_temperature(self.core.extract_temperature)

    @property
    def supply_temperature(self) -> float | None:
        return plausible_temperature(self.core.supply_temperature)

    @property
    def exhaust_temperature(self) -> float | None:
        return plausible_temperature(self.core.exhaust_temperature)

    @property
    def gwc_temperature(self) -> float | None:
        return plausible_temperature(self.core.gwc_temperature)

    @property
    def heater_control_temperature(self) -> float | None:
        return plausible_temperature(self.core.heater_control_temperature)

    @property
    def secondary_heating_temperature(self) -> float | None:
        return plausible_temperature(self.core.secondary_heating_temperature)

    @property
    def efficiency(self) -> float | None:
        return heat_recovery_efficiency(
            self.outdoor_temperature,
            self.supply_temperature,
            self.extract_temperature,
            bypass_active=self.core.bypass_active,
        )

    @property
    def recovered_power(self) -> float | None:
        return recovered_power(
            self.outdoor_temperature,
            self.supply_temperature,
            self.core.supply_flow,
            bypass_active=self.core.bypass_active,
        )

    @property
    def has_error(self) -> bool | None:
        errors = self.core.errors
        return None if errors is None else int(errors) != 0

    @property
    def error_keys(self) -> list[str] | None:
        return error_keys(self.core.errors)

    @property
    def clock(self) -> datetime | None:
        """Czas lokalny sterownika, bez strefy."""
        return decode_clock(self.core.clock_date, self.core.clock_time)

    async def async_set_clock(self, now: datetime) -> None:
        await self.core.write("clock_date", encode_date(now.date()))
        await self.core.write("clock_time", encode_time(now.time()))
