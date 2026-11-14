"""Warstwa urządzenia na symulowanej centrali, bez Home Assistanta."""

from __future__ import annotations

from datetime import datetime

from modbus_connection import (
    IllegalDataAddressError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest

from custom_components.defro_air.device import CORE, EXTENDED, Core, DefroAir, Extended


async def test_old_firmware_values(old_unit: MockModbusUnit) -> None:
    """Prawdziwy zrzut z modułu MBP 1.1.4 dekoduje się jak na panelu."""
    device = DefroAir(old_unit)
    report = await device.async_update()

    assert report.updated == {CORE}
    assert not report.failed
    assert device.components == (CORE,)
    assert device.extended is None

    core = device.core
    assert (core.supply_flow, core.extract_flow) == (78, 83)
    assert (core.supply_gear, core.extract_gear) == (1, 1)
    assert device.outdoor_temperature == 6.2
    assert device.extract_temperature == 21.4
    assert device.supply_temperature == 19.4
    assert device.exhaust_temperature == 11.7
    assert device.heater_control_temperature == 7.2
    # Niepodłączone czujniki zwracają 1715.
    assert device.gwc_temperature is None
    assert device.secondary_heating_temperature is None
    assert device.efficiency == 86.8
    assert device.recovered_power == 345
    assert device.has_error is False
    assert device.error_keys == []
    assert device.clock == datetime(2026, 11, 14, 16, 16)
    assert core.bypass_active is False
    assert core.bypass_enabled is False
    assert core.holiday_days == 0


async def test_poll_is_one_block(old_unit: MockModbusUnit) -> None:
    """Po rozpoznaniu wersji programu odczyt to jedno zapytanie 100–155."""
    device = DefroAir(old_unit)
    await device.async_update()
    old_unit.read_events.clear()

    await device.async_update()

    assert [(e.register_type, e.address, e.count) for e in old_unit.read_events] == [
        ("holding", 100, 56)
    ]


async def test_new_firmware_serves_extended(new_unit: MockModbusUnit) -> None:
    device = DefroAir(new_unit)
    report = await device.async_update()

    assert report.updated == {CORE, EXTENDED}
    assert device.components == (CORE, EXTENDED)
    extended = device.extended
    assert extended is not None
    assert extended.weekly_enabled is True
    assert extended.target_gear == 2
    assert extended.windows_mode is False
    assert (extended.gear_1_flow, extended.gear_2_flow, extended.gear_3_flow) == (
        90,
        180,
        300,
    )
    assert extended.flow_balancing is True
    assert extended.software_version == 2161
    assert extended.bypass_comfort_temperature == 22

    new_unit.read_events.clear()
    await device.async_update()
    assert [(e.address, e.count) for e in new_unit.read_events] == [(100, 56), (156, 19)]


async def test_negative_temperature(old_unit: MockModbusUnit) -> None:
    """Instrukcja: 65490 → −4,6 °C, 65535 → −0,1 °C."""
    old_unit.holding[104] = 65490
    old_unit.holding[107] = 65535
    device = DefroAir(old_unit)
    await device.async_update()

    assert device.outdoor_temperature == -4.6
    assert device.exhaust_temperature == -0.1


async def test_sensor_error_value(old_unit: MockModbusUnit) -> None:
    """63066 to według instrukcji błąd czujnika."""
    old_unit.holding[106] = 63066
    device = DefroAir(old_unit)
    await device.async_update()

    assert device.supply_temperature is None
    assert device.efficiency is None
    assert device.recovered_power is None


async def test_errors(old_unit: MockModbusUnit) -> None:
    old_unit.holding[139] = 0b0000_0000_0010_0001
    device = DefroAir(old_unit)
    await device.async_update()

    assert device.has_error is True
    assert device.error_keys == ["exhaust_fan", "exhaust_sensor"]


async def test_bypass_hides_efficiency(old_unit: MockModbusUnit) -> None:
    old_unit.holding[133] = 1
    device = DefroAir(old_unit)
    await device.async_update()

    assert device.core.bypass_active is True
    assert device.efficiency is None
    assert device.recovered_power is None


async def test_writes(old_unit: MockModbusUnit, writes: list[WriteEvent]) -> None:
    device = DefroAir(old_unit)
    await device.async_update()

    await device.core.write("bypass_enabled", True)
    await device.core.write("holiday_days", 7)
    await device.core.write("party", 90)

    assert [(w.address, w.values, w.function_code) for w in writes] == [
        (141, [1], 6),
        (145, [7], 6),
        (147, [90], 6),
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("holiday_days", 61),
        ("holiday_days", -1),
        ("fireplace", 181),
        ("party", 721),
        ("party", 1.5),
        ("party", True),
    ],
)
async def test_out_of_range_write_is_rejected(
    old_unit: MockModbusUnit, writes: list[WriteEvent], field: str, value: object
) -> None:
    device = DefroAir(old_unit)
    await device.async_update()

    with pytest.raises(ValueError):
        await device.core.write(field, value)
    assert not writes


async def test_read_only_field_cannot_be_written(old_unit: MockModbusUnit) -> None:
    device = DefroAir(old_unit)
    await device.async_update()

    with pytest.raises(Exception):
        await device.core.write("supply_flow", 100)


async def test_set_clock(old_unit: MockModbusUnit, writes: list[WriteEvent]) -> None:
    device = DefroAir(old_unit)
    await device.async_update()

    await device.async_set_clock(datetime(2027, 3, 9, 7, 45, 59))
    await device.async_update()

    assert [(w.address, w.values) for w in writes] == [
        (152, [(9 << 11) | (3 << 7) | 27]),
        (153, [(7 << 8) | 45]),
    ]
    assert device.clock == datetime(2027, 3, 9, 7, 45)


async def test_new_firmware_gear_write(
    new_unit: MockModbusUnit, writes: list[WriteEvent]
) -> None:
    device = DefroAir(new_unit)
    await device.async_update()
    assert device.extended is not None

    await device.extended.write("target_gear", 3)
    with pytest.raises(ValueError):
        await device.extended.write("target_gear", 4)

    assert [(w.address, w.values) for w in writes] == [(157, [3])]


def test_link_settings_are_not_fields() -> None:
    """Rejestry 126–128 zmieniają parametry transmisji: nie wolno ich wystawiać."""
    addresses = {
        field.address
        for component in (Core, Extended)
        for field in component.declared_fields.values()
    }
    assert {100, 141, 155, 157} <= addresses
    assert not addresses & {126, 127, 128}


async def test_unreachable_device_raises(old_unit: MockModbusUnit) -> None:
    old_unit.fail_requests(ModbusTimeoutError())

    with pytest.raises(ModbusTimeoutError):
        await DefroAir(old_unit).async_update()


async def test_core_refused_is_reported(mock_modbus_unit: MockModbusUnit) -> None:
    """Urządzenie, które nie zna rejestrów 100–155, to nie jest ta centrala."""
    mock_modbus_unit.fail_read(100, IllegalDataAddressError())
    mock_modbus_unit.fail_read(156, IllegalDataAddressError())

    report = await DefroAir(mock_modbus_unit).async_update()

    assert not report.updated
    assert isinstance(report.failed[CORE], IllegalDataAddressError)


async def test_setup_is_retried_after_failure(old_unit: MockModbusUnit) -> None:
    """Nieudane rozpoznanie wersji programu jest ponawiane przy kolejnym odczycie."""
    old_unit.fail_requests(ModbusTimeoutError())
    device = DefroAir(old_unit)
    with pytest.raises(ModbusTimeoutError):
        await device.async_update()

    old_unit.fail_requests(None)
    report = await device.async_update()

    assert report.updated == {CORE}
    assert device.components == (CORE,)
