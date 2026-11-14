"""Integracja Defro Air: rekuperator Defro po Modbus."""

from __future__ import annotations

from modbus_connection import ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_UNIT_ID
from .coordinator import DefroAirConfigEntry, DefroAirCoordinator
from .device import DefroAir

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: DefroAirConfigEntry) -> bool:
    """Skonfiguruj centralę z wpisu konfiguracji."""
    # Połączenie należy do integracji modbus: jest współdzielone z innymi
    # integracjami na tej samej bramce i zamykane, gdy zwolni je ostatni wpis.
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT_ID],
    )

    coordinator = DefroAirCoordinator(hass, entry, DefroAir(unit))
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DefroAirConfigEntry) -> bool:
    """Wyładuj wpis konfiguracji."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
