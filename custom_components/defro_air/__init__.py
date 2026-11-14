"""Integracja Defro Air: rekuperator Defro po Modbus."""

from __future__ import annotations

from pathlib import Path

from modbus_connection import ModbusTcpParams

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import DefroAirConfigEntry, DefroAirCoordinator
from .device import DefroAir

CARD_URL = f"/{DOMAIN}/defro-air-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "defro-air-card.js"
DATA_CARD_REGISTERED = f"{DOMAIN}_card_registered"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def _async_register_card(hass: HomeAssistant) -> None:
    """Udostępnij kartę dashboardu i załaduj ją we frontendzie (raz na uruchomienie)."""
    if hass.data.get(DATA_CARD_REGISTERED):
        return
    hass.data[DATA_CARD_REGISTERED] = True

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), cache_headers=False)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_URL}?v={integration.version}"
    if not await _async_register_resource(hass, url):
        # zasoby w YAML-u
        add_extra_js_url(hass, url)


def _storage_resources(hass: HomeAssistant) -> ResourceStorageCollection | None:
    """Zasoby dashboardu, jeśli są zarządzane z interfejsu (a nie w YAML-u)."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or lovelace.resource_mode != MODE_STORAGE:
        return None
    resources = lovelace.resources
    return resources if isinstance(resources, ResourceStorageCollection) else None


async def _async_register_resource(hass: HomeAssistant, url: str) -> bool:
    if (resources := _storage_resources(hass)) is None:
        return False
    await resources.async_get_info()
    for item in resources.async_items():
        if item["url"].split("?")[0] != CARD_URL:
            continue
        if item["url"] != url:
            await resources.async_update_item(
                item["id"], {"res_type": "module", "url": url}
            )
        return True
    await resources.async_create_item({"res_type": "module", "url": url})
    return True


async def async_remove_entry(hass: HomeAssistant, entry: DefroAirConfigEntry) -> None:
    """Po usunięciu ostatniej centrali usuń kartę z zasobów dashboardu."""
    if hass.config_entries.async_entries(DOMAIN):
        return
    if (resources := _storage_resources(hass)) is None:
        return
    await resources.async_get_info()
    for item in list(resources.async_items()):
        if item["url"].split("?")[0] == CARD_URL:
            await resources.async_delete_item(item["id"])


async def async_setup_entry(hass: HomeAssistant, entry: DefroAirConfigEntry) -> bool:
    await _async_register_card(hass)

    # Połączenie jest współdzielone przez integrację modbus.
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
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
