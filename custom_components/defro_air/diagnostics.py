"""Diagnostyka integracji Defro Air."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import DefroAirConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DefroAirConfigEntry
) -> dict[str, Any]:
    """Surowe rejestry w formacie ``modbus_connection.mock.load_raw``."""
    coordinator = entry.runtime_data
    device = coordinator.device
    return {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "components": list(device.components),
        "updated": sorted(coordinator.data.updated),
        "failed": {
            component: str(error) or type(error).__name__
            for component, error in coordinator.data.failed.items()
        },
        "raw": await device.async_read_all_raw(),
    }
