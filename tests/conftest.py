"""Wspólne elementy testów: symulowana centrala i prawdziwy Home Assistant."""

from __future__ import annotations

from collections.abc import Iterator
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.defro_air.const import CONF_UNIT_ID, DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"

HOST = "192.0.2.10"
PORT = 8899
UNIT_ID = 1
ENTRY_DATA = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_UNIT_ID: UNIT_ID}

# Rejestry 156–174 w postaci, w jakiej opisuje je instrukcja programu 2.1.61.
EXTENDED_REGISTERS = {
    156: 1,  # tygodniówka
    157: 2,  # bieg zadany
    158: 0,  # okna
    159: 0,
    160: 0,
    161: 30,
    162: 55,
    163: 90,
    164: 90,
    165: 180,
    166: 300,
    167: 0,
    168: 1,  # flow balancing
    169: 0,
    170: 412,
    171: 2161,
    172: 400,
    173: 15,
    174: 22,
}


def load_old_firmware(unit: MockModbusUnit) -> None:
    """Centrala z modułem MBP 1.1.4: prawdziwy zrzut, zakres 156+ odrzucany."""
    unit.load_raw(json.loads((FIXTURES / "mbp_1_1_4.json").read_text()))
    unit.fail_read(156, IllegalDataAddressError())


def load_new_firmware(unit: MockModbusUnit) -> None:
    """Centrala z nowszym programem: ten sam zrzut plus rejestry 156–174."""
    unit.load_raw(json.loads((FIXTURES / "mbp_1_1_4.json").read_text()))
    for address, value in EXTENDED_REGISTERS.items():
        unit.holding[address] = value


@pytest.fixture
def old_unit(mock_modbus_unit: MockModbusUnit) -> MockModbusUnit:
    load_old_firmware(mock_modbus_unit)
    return mock_modbus_unit


@pytest.fixture
def new_unit(mock_modbus_unit: MockModbusUnit) -> MockModbusUnit:
    load_new_firmware(mock_modbus_unit)
    return mock_modbus_unit


@pytest.fixture
def writes(mock_modbus_unit: MockModbusUnit) -> list[WriteEvent]:
    """Lista zapisów wykonanych na symulowanej centrali."""
    events: list[WriteEvent] = []
    mock_modbus_unit.on_write(events.append)
    return events


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Pozwól Home Assistantowi ładować integrację z custom_components."""


@pytest.fixture(autouse=True)
def _mock_modbus_link(mock_modbus_connection: MockModbusConnection) -> Iterator[None]:
    """Podmień połączenie integracji modbus na symulowane, w pamięci.

    Prawdziwe połączenie po zamknięciu jest tworzone od nowa. Tu za każdym
    razem wraca ten sam obiekt, więc jego zamknięcie nie może być trwałe.
    """
    mock_modbus_connection.close = AsyncMock()
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        return_value=mock_modbus_connection,
    ):
        yield


@pytest.fixture(autouse=True)
def _no_integration_errors(
    request: pytest.FixtureRequest, caplog: pytest.LogCaptureFixture
) -> Iterator[None]:
    """Każdy test pada, jeśli integracja zapisała błąd w logu."""
    yield
    if request.node.get_closest_marker("allow_errors"):
        return
    errors = [
        record
        for record in caplog.get_records("call")
        if record.levelno >= logging.ERROR
        and (DOMAIN in record.name or DOMAIN in record.getMessage())
    ]
    assert not errors, [record.getMessage() for record in errors]


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "allow_errors: test celowo wywołuje błąd zapisywany w logu"
    )


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Wpis konfiguracji, jeszcze niezaładowany."""
    config_entry = MockConfigEntry(domain=DOMAIN, title="Defro Air", data=ENTRY_DATA)
    config_entry.add_to_hass(hass)
    return config_entry


async def setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Załaduj wpis i poczekaj, aż Home Assistant skończy pracę."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def device_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> dr.DeviceEntry:
    """Jedyne urządzenie wpisu w rejestrze urządzeń."""
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), config_entry.entry_id
    )
    assert len(devices) == 1
    return devices[0]


def entity_id(hass: HomeAssistant, config_entry: MockConfigEntry, platform: str, key: str):
    """Identyfikator encji po jej kluczu, niezależnie od języka nazw."""
    return er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{config_entry.entry_id}_{key}"
    )


def state(hass: HomeAssistant, config_entry: MockConfigEntry, platform: str, key: str):
    """Stan encji o danym kluczu; pada, jeśli encja nie istnieje."""
    found = entity_id(hass, config_entry, platform, key)
    assert found is not None, f"brak encji {platform}.{key}"
    result = hass.states.get(found)
    assert result is not None, f"encja {found} nie ma stanu"
    return result
