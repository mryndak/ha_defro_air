"""Integracja załadowana w prawdziwym Home Assistancie, na symulowanej centrali."""

from __future__ import annotations

from datetime import datetime, timedelta

from modbus_connection import (
    IllegalDataValueError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.defro_air.const import DOMAIN
from custom_components.defro_air.diagnostics import async_get_config_entry_diagnostics

from .conftest import HOST, device_entry, entity_id, setup, state


async def _poll(hass: HomeAssistant, seconds: int = 16) -> None:
    """Przesuń czas o jeden cykl odczytu."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


def _written(writes: list[WriteEvent]) -> list[tuple[int, list[int]]]:
    return [(w.address, list(w.values)) for w in writes]


# --- stary program (MBP 1.1.4) ---------------------------------------------


async def test_old_firmware_sensors(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    def value(key: str) -> str:
        return state(hass, entry, "sensor", key).state

    assert value("supply_flow") == "78"
    assert value("extract_flow") == "83"
    assert value("supply_gear") == "1"
    assert value("extract_gear") == "1"
    assert value("outdoor_temperature") == "6.2"
    assert value("extract_temperature") == "21.4"
    assert value("supply_temperature") == "19.4"
    assert value("exhaust_temperature") == "11.7"
    assert value("heater_control_temperature") == "7.2"
    assert value("efficiency") == "86.8"
    assert value("recovered_power") == "345"
    assert value("filter_days") == "0"
    assert value("error_code") == "0"
    assert state(hass, entry, "sensor", "error_code").attributes["errors"] == []

    assert state(hass, entry, "binary_sensor", "problem").state == STATE_OFF
    assert state(hass, entry, "binary_sensor", "bypass_active").state == STATE_OFF
    assert state(hass, entry, "binary_sensor", "antifreeze_active").state == STATE_OFF
    assert state(hass, entry, "binary_sensor", "holiday_active").state == STATE_OFF
    assert state(hass, entry, "switch", "bypass_enabled").state == STATE_OFF
    assert state(hass, entry, "number", "holiday_days").state == "0"
    assert state(hass, entry, "number", "party").state == "0"
    assert state(hass, entry, "number", "fireplace").state == "0"
    assert state(hass, entry, "button", "sync_clock").state == STATE_UNKNOWN


async def test_old_firmware_has_no_extended_entities(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    """Bez rejestrów 156–174 nie powstaje wentylator ani nastawy z tego zakresu."""
    await setup(hass, entry)

    for platform, key in (
        ("fan", "ventilation"),
        ("switch", "weekly_enabled"),
        ("switch", "windows_mode"),
        ("number", "gear_1_flow"),
        ("number", "bypass_comfort_temperature"),
        ("sensor", "filter_runtime"),
    ):
        assert entity_id(hass, entry, platform, key) is None, key


async def test_optional_sensors_are_disabled_by_default(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    registry = er.async_get(hass)

    for platform, key in (
        ("sensor", "gwc_temperature"),
        ("sensor", "secondary_heating_temperature"),
        ("sensor", "clock"),
        ("switch", "gwc_enabled"),
        ("binary_sensor", "digital_input_hood"),
    ):
        found = entity_id(hass, entry, platform, key)
        assert found is not None, key
        assert registry.async_get(found).disabled_by is not None, key


async def test_device_registry(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)

    device = device_entry(hass, entry)
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == "Defro"
    assert device.name == "Defro Air"
    # Wszystkie encje wpisu należą do tego jednego urządzenia.
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert entities
    assert {e.device_id for e in entities} == {device.id}


async def test_values_follow_the_unit(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)

    old_unit.holding[104] = 65490  # −4,6 °C
    old_unit.holding[102] = 3
    old_unit.holding[133] = 1  # bypass otwarty
    old_unit.holding[139] = 0b10_0001  # dwa błędy
    await _poll(hass)

    assert state(hass, entry, "sensor", "outdoor_temperature").state == "-4.6"
    assert state(hass, entry, "sensor", "supply_gear").state == "3"
    assert state(hass, entry, "binary_sensor", "bypass_active").state == STATE_ON
    assert state(hass, entry, "binary_sensor", "problem").state == STATE_ON
    assert state(hass, entry, "sensor", "error_code").attributes["errors"] == [
        "exhaust_fan",
        "exhaust_sensor",
    ]
    # Przy otwartym bypassie sprawność nie jest liczona.
    assert state(hass, entry, "sensor", "efficiency").state == STATE_UNKNOWN


async def test_bypass_switch(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
) -> None:
    await setup(hass, entry)
    switch = entity_id(hass, entry, "switch", "bypass_enabled")

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch}, blocking=True
    )
    await hass.async_block_till_done()
    assert _written(writes) == [(141, [1])]
    assert hass.states.get(switch).state == STATE_ON

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch}, blocking=True
    )
    await hass.async_block_till_done()
    assert _written(writes) == [(141, [1]), (141, [0])]
    assert hass.states.get(switch).state == STATE_OFF


@pytest.mark.parametrize(
    ("key", "address", "value"),
    [("holiday_days", 145, 14), ("party", 147, 120), ("fireplace", 146, 180)],
)
async def test_numbers(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
    key: str,
    address: int,
    value: int,
) -> None:
    await setup(hass, entry)
    number = entity_id(hass, entry, "number", key)

    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": value}, blocking=True
    )
    await hass.async_block_till_done()

    assert _written(writes) == [(address, [value])]
    assert hass.states.get(number).state == str(value)


async def test_number_out_of_range_is_rejected(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
) -> None:
    await setup(hass, entry)
    number = entity_id(hass, entry, "number", "holiday_days")

    with pytest.raises(Exception):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": number, "value": 61}, blocking=True
        )
    assert not writes


async def test_sync_clock_button(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
    freezer,
) -> None:
    """Przycisk zapisuje czas lokalny Home Assistanta, nie UTC."""
    await hass.config.async_set_time_zone("Europe/Warsaw")
    freezer.move_to(datetime(2027, 1, 5, 6, 30, tzinfo=dt_util.UTC))  # 07:30 w PL
    await setup(hass, entry)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id(hass, entry, "button", "sync_clock")},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _written(writes) == [
        (152, [(5 << 11) | (1 << 7) | 27]),
        (153, [(7 << 8) | 30]),
    ]


@pytest.mark.allow_errors
async def test_refused_write_raises(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    old_unit.fail_write(141, IllegalDataValueError())
    switch = entity_id(hass, entry, "switch", "bypass_enabled")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert hass.states.get(switch).state == STATE_OFF


@pytest.mark.allow_errors
async def test_unreachable_then_back(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)
    sensor = entity_id(hass, entry, "sensor", "supply_temperature")
    assert hass.states.get(sensor).state == "19.4"

    old_unit.fail_requests(ModbusTimeoutError())
    await _poll(hass)
    assert hass.states.get(sensor).state == STATE_UNAVAILABLE

    old_unit.fail_requests(None)
    old_unit.holding[106] = 201
    await _poll(hass)
    assert hass.states.get(sensor).state == "20.1"


@pytest.mark.allow_errors
async def test_link_is_reopened_after_repeated_timeouts(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    mock_modbus_connection,
) -> None:
    await setup(hass, entry)
    await old_unit.read_holding_registers(100, 1)
    assert mock_modbus_connection.connected is True

    old_unit.fail_requests(ModbusTimeoutError())
    for _ in range(3):
        await _poll(hass)

    assert mock_modbus_connection.connected is False


async def test_setup_retries_when_unit_is_off(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    old_unit.fail_requests(ModbusTimeoutError())

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    mock_modbus_connection,
) -> None:
    await setup(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert (
        state(hass, entry, "sensor", "supply_temperature").state == STATE_UNAVAILABLE
    )


async def test_diagnostics(
    hass: HomeAssistant, old_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["data"]["host"] != HOST
    assert result["components"] == ["core"]
    assert result["updated"] == ["core"]
    assert result["failed"] == {}
    assert result["raw"]["holding"][105] == 214
    assert set(result["raw"]["holding"]) == set(range(100, 156))


async def test_dashboard_card_is_served(
    hass: HomeAssistant,
    old_unit: MockModbusUnit,
    entry: MockConfigEntry,
    hass_client,
) -> None:
    """Integracja udostępnia kartę dashboardu i ładuje ją we frontendzie."""
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    await setup(hass, entry)

    client = await hass_client()
    response = await client.get("/defro_air/defro-air-card.js")
    assert response.status == 200
    body = await response.text()
    assert 'customElements.define("defro-air-card"' in body

    urls = hass.data[DATA_EXTRA_MODULE_URL].urls
    assert [u for u in urls if u.startswith("/defro_air/defro-air-card.js?v=")]

    # Przeładowanie wpisu nie rejestruje karty drugi raz.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len([u for u in hass.data[DATA_EXTRA_MODULE_URL].urls if "defro-air-card" in u]) == 1


def test_card_uses_existing_entity_keys() -> None:
    """Karta szuka encji po kluczach; każdy musi istnieć w integracji."""
    import re

    from custom_components.defro_air import CARD_PATH
    from custom_components.defro_air.binary_sensor import BINARY_SENSORS
    from custom_components.defro_air.number import NUMBERS
    from custom_components.defro_air.sensor import SENSORS
    from custom_components.defro_air.switch import SWITCHES

    known = (
        {f"sensor.{d.key}" for d in SENSORS}
        | {f"binary_sensor.{d.key}" for d in BINARY_SENSORS}
        | {f"switch.{d.key}" for d in SWITCHES}
        | {f"number.{d.key}" for d in NUMBERS}
        | {"fan.ventilation"}
    )
    used = set(
        re.findall(
            r'"((?:sensor|binary_sensor|switch|number|fan)\.[a-z0-9_]+)"',
            CARD_PATH.read_text(encoding="utf-8"),
        )
    )
    assert used, "karta nie odwołuje się do żadnej encji"
    assert used <= known, sorted(used - known)


# --- nowszy program (rejestry 156–174) -------------------------------------


async def test_new_firmware_entities(
    hass: HomeAssistant, new_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    await setup(hass, entry)

    fan = state(hass, entry, "fan", "ventilation")
    assert fan.state == STATE_ON
    assert fan.attributes["percentage"] == 66
    assert state(hass, entry, "switch", "weekly_enabled").state == STATE_ON
    assert state(hass, entry, "switch", "windows_mode").state == STATE_OFF
    assert state(hass, entry, "sensor", "filter_runtime").state == "412"
    assert state(hass, entry, "sensor", "unit_size").state == "400"

    assert device_entry(hass, entry).sw_version == "2161"


@pytest.mark.parametrize(
    ("percentage", "gear"), [(1, 1), (33, 1), (34, 2), (66, 2), (67, 3), (100, 3), (0, 0)]
)
async def test_fan_percentage_sets_gear(
    hass: HomeAssistant,
    new_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
    percentage: int,
    gear: int,
) -> None:
    await setup(hass, entry)

    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": entity_id(hass, entry, "fan", "ventilation"), "percentage": percentage},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _written(writes) == [(157, [gear])]


async def test_fan_turn_off_and_on(
    hass: HomeAssistant,
    new_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
) -> None:
    await setup(hass, entry)
    fan = entity_id(hass, entry, "fan", "ventilation")

    await hass.services.async_call("fan", "turn_off", {"entity_id": fan}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(fan).state == STATE_OFF

    await hass.services.async_call("fan", "turn_on", {"entity_id": fan}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(fan).state == STATE_ON
    assert hass.states.get(fan).attributes["percentage"] == 33

    assert _written(writes) == [(157, [0]), (157, [1])]


async def test_windows_switch(
    hass: HomeAssistant,
    new_unit: MockModbusUnit,
    entry: MockConfigEntry,
    writes: list[WriteEvent],
) -> None:
    await setup(hass, entry)

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id(hass, entry, "switch", "windows_mode")},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _written(writes) == [(158, [1])]
    assert state(hass, entry, "switch", "windows_mode").state == STATE_ON


async def test_extended_failure_keeps_core_available(
    hass: HomeAssistant, new_unit: MockModbusUnit, entry: MockConfigEntry
) -> None:
    """Gdy zakres 156+ przestaje odpowiadać, encje z zakresu 100–155 działają dalej."""
    await setup(hass, entry)

    new_unit.fail_read(156, ModbusTimeoutError())
    await _poll(hass)

    assert state(hass, entry, "fan", "ventilation").state == STATE_UNAVAILABLE
    assert state(hass, entry, "sensor", "supply_temperature").state == "19.4"
