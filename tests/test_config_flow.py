"""Konfiguracja z interfejsu: dodanie, błędy, zmiana adresu, opcje."""

from __future__ import annotations

from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit, WriteEvent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.defro_air.const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DOMAIN,
)

from .conftest import ENTRY_DATA, HOST, PORT, UNIT_ID, setup


async def _start(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]
    return result


async def test_user_flow_creates_entry(
    hass: HomeAssistant, old_unit: MockModbusUnit, writes: list[WriteEvent]
) -> None:
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ENTRY_DATA)
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Defro Air"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: PORT, CONF_UNIT_ID: UNIT_ID}
    # Sprawdzenie połączenia niczego nie zapisuje do centrali.
    assert not writes


async def test_port_and_unit_are_stored_as_integers(
    hass: HomeAssistant, old_unit: MockModbusUnit
) -> None:
    """Pola liczbowe formularza zwracają float; we wpisie mają być int."""
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: 8899.0, CONF_UNIT_ID: 1.0}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert type(result["data"][CONF_PORT]) is int
    assert type(result["data"][CONF_UNIT_ID]) is int


async def test_cannot_connect_then_recover(
    hass: HomeAssistant, old_unit: MockModbusUnit
) -> None:
    old_unit.fail_requests(ModbusTimeoutError())
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ENTRY_DATA)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    old_unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ENTRY_DATA)
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_unsupported_device(
    hass: HomeAssistant, mock_modbus_unit: MockModbusUnit
) -> None:
    """Coś odpowiada po Modbus, ale nie ma rejestrów sterownika Defro."""
    mock_modbus_unit.fail_read(100, IllegalDataAddressError())
    mock_modbus_unit.fail_read(156, IllegalDataAddressError())
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ENTRY_DATA)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device"}


async def test_duplicate_is_aborted(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(ENTRY_DATA)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_second_unit_on_same_gateway_is_allowed(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    mock_modbus_connection,
) -> None:
    from .conftest import load_old_firmware

    load_old_firmware(mock_modbus_connection.for_unit(2))
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ENTRY_DATA, CONF_UNIT_ID: 2}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_changes_address(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.99", CONF_PORT: 502, CONF_UNIT_ID: 1}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "192.0.2.99", CONF_PORT: 502, CONF_UNIT_ID: 1}


async def test_reconfigure_keeps_address_when_unreachable(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    result = await entry.start_reconfigure_flow(hass)

    old_unit.fail_requests(ModbusTimeoutError())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.99", CONF_PORT: 502, CONF_UNIT_ID: 1}
    )
    old_unit.fail_requests(None)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == ENTRY_DATA


async def test_options_change_poll_interval(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert entry.runtime_data.update_interval.total_seconds() == 15

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 60}
    # Zmiana opcji przeładowuje wpis, więc koordynator ma nowy odstęp.
    assert entry.runtime_data.update_interval.total_seconds() == 60
