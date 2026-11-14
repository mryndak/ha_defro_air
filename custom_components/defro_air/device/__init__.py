"""Rekuperator Defro Air po Modbus, bez zależności od Home Assistanta.

Pakiet dostaje gotowy ``ModbusUnit`` i tylko czyta oraz zapisuje rejestry.
Połączenie otwiera i zamyka ten, kto go używa.
"""

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
    """Centrala wentylacyjna Defro Air ze sterownikiem ST-340 v2."""

    def __init__(self, unit: ModbusUnit) -> None:
        super().__init__(unit)
        self.core = Core(unit)
        self.extended: Extended | None = None

    async def _async_setup(self) -> None:
        """Sprawdź raz, czy program sterownika obsługuje rejestry 156–174."""
        self.extended = await read_optional(Extended(self.modbus_unit))

    @property
    def components(self) -> tuple[str, ...]:
        """Podsystemy, które to urządzenie obsługuje (znane po pierwszym odczycie)."""
        return (CORE, EXTENDED) if self.extended is not None else (CORE,)

    async def async_update(self) -> UpdateReport:
        """Odczytaj wszystkie obsługiwane rejestry."""
        return await self.async_poll((CORE, EXTENDED))

    async def async_read_all_raw(self) -> dict[str, dict[int, int | bool]]:
        """Surowe wartości wszystkich obsługiwanych rejestrów (do diagnostyki)."""
        return await self.async_read_raw((CORE, EXTENDED))

    # --- wartości pochodne -------------------------------------------------

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
        """Sprawność odzysku ciepła w procentach."""
        return heat_recovery_efficiency(
            self.outdoor_temperature,
            self.supply_temperature,
            self.extract_temperature,
            bypass_active=self.core.bypass_active,
        )

    @property
    def recovered_power(self) -> float | None:
        """Moc odzyskiwana przez wymiennik w watach."""
        return recovered_power(
            self.outdoor_temperature,
            self.supply_temperature,
            self.core.supply_flow,
            bypass_active=self.core.bypass_active,
        )

    @property
    def has_error(self) -> bool | None:
        """Czy sterownik zgłasza jakikolwiek błąd."""
        errors = self.core.errors
        return None if errors is None else int(errors) != 0

    @property
    def error_keys(self) -> list[str] | None:
        """Nazwy aktywnych błędów."""
        return error_keys(self.core.errors)

    @property
    def clock(self) -> datetime | None:
        """Data i godzina ustawione w sterowniku (czas lokalny, bez strefy)."""
        return decode_clock(self.core.clock_date, self.core.clock_time)

    # --- zapisy ------------------------------------------------------------

    async def async_set_clock(self, now: datetime) -> None:
        """Ustaw datę i godzinę sterownika (podaj czas lokalny)."""
        await self.core.write("clock_date", encode_date(now.date()))
        await self.core.write("clock_time", encode_time(now.time()))
