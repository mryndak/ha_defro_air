"""Rejestry sterownika ST-340 v2 (instrukcja „ST-340 v2 Medium DEFRO”, program 2.1.61).

Rejestry 126–128 (adres i parametry transmisji) są pominięte celowo:
ich zapis zerwałby łączność.
"""

from __future__ import annotations

from collections.abc import Callable

from modbus_connection.model import (
    Component,
    boolean,
    flags,
    gauge,
    integer,
    raw_register,
)

from .codec import TEMPERATURE_UNAVAILABLE, ErrorFlags

FLOW_UNIT = "m³/h"
TEMPERATURE_UNIT = "°C"

MAX_GEAR = 3
MAX_HOLIDAY_DAYS = 60
MAX_FIREPLACE = 180
MAX_PARTY = 720


def _in_range(low: int, high: int) -> Callable[[int], int]:
    def validate(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"oczekiwano liczby całkowitej, jest {value!r}")
        if not low <= value <= high:
            raise ValueError(f"wartość {value} poza zakresem {low}–{high}")
        return value

    return validate


def _temperature(address: int):
    return gauge(address, 0.1, nan=TEMPERATURE_UNAVAILABLE, unit=TEMPERATURE_UNIT)


class Core(Component):
    """Rejestry 100–155, dostępne w każdej wersji programu."""

    register_ranges = ((100, 155),)

    supply_flow = integer(100, signed=False, unit=FLOW_UNIT)
    extract_flow = integer(101, signed=False, unit=FLOW_UNIT)
    # 0–3, w trybie urlop 4 (moc minimalna)
    supply_gear = integer(102, signed=False)
    extract_gear = integer(103, signed=False)

    # 105 i 107 są w instrukcji zamienione miejscami
    outdoor_temperature = _temperature(104)
    extract_temperature = _temperature(105)
    supply_temperature = _temperature(106)
    exhaust_temperature = _temperature(107)
    gwc_temperature = _temperature(108)
    heater_control_temperature = _temperature(109)

    schedule_day = integer(110, signed=False)
    schedule_zone_0 = integer(111, signed=False)
    schedule_zone_1 = integer(112, signed=False)
    schedule_zone_2 = integer(113, signed=False)
    schedule_zone_3 = integer(114, signed=False)
    schedule_zone_4 = integer(115, signed=False)
    schedule_gear_0 = integer(116, signed=False)
    schedule_gear_1 = integer(117, signed=False)
    schedule_gear_2 = integer(118, signed=False)
    schedule_gear_3 = integer(119, signed=False)
    schedule_gear_4 = integer(120, signed=False)

    gwc_active = boolean(132)
    bypass_active = boolean(133)
    secondary_heating_active = boolean(135)
    holiday_active = boolean(137)
    filter_days = integer(138, signed=False)
    errors = flags(139, ErrorFlags)

    gwc_enabled = boolean(140, writable=True)
    bypass_enabled = boolean(141, writable=True)
    secondary_heating_enabled = boolean(143)
    holiday_days = integer(
        145, signed=False, writable=_in_range(0, MAX_HOLIDAY_DAYS), unit="d"
    )
    # sekundy; nawiew na biegu 3, wywiew stoi
    fireplace = integer(146, signed=False, writable=_in_range(0, MAX_FIREPLACE))
    # minuty; sterownik podnosi 1–14 do 15
    party = integer(147, signed=False, writable=_in_range(0, MAX_PARTY))

    digital_input_gear_3 = boolean(149)
    digital_input_hood = boolean(150)

    clock_date = raw_register(152, writable=True)
    clock_time = raw_register(153, writable=True)

    antifreeze_active = boolean(154)
    secondary_heating_temperature = _temperature(155)


class Extended(Component):
    """Rejestry 156–174, tylko w nowszych wersjach programu (nie w MBP 1.1.4)."""

    register_ranges = ((156, 174),)

    weekly_enabled = boolean(156, writable=True)
    target_gear = integer(157, signed=False, writable=_in_range(0, MAX_GEAR))
    windows_mode = boolean(158, writable=True)
    humidifier_enabled = boolean(159, writable=True)
    humidifier_heater_enabled = boolean(160, writable=True)

    gear_1_power = integer(161, signed=False, writable=_in_range(1, 100), unit="%")
    gear_2_power = integer(162, signed=False, writable=_in_range(1, 100), unit="%")
    gear_3_power = integer(163, signed=False, writable=_in_range(1, 100), unit="%")
    gear_1_flow = integer(164, signed=False, writable=_in_range(0, 1342), unit=FLOW_UNIT)
    gear_2_flow = integer(165, signed=False, writable=_in_range(0, 1342), unit=FLOW_UNIT)
    gear_3_flow = integer(166, signed=False, writable=_in_range(0, 1342), unit=FLOW_UNIT)

    flow_balancing = boolean(168, writable=True)
    enthalpy_exchanger = boolean(169, writable=True)
    filter_runtime = integer(170, signed=False)
    software_version = integer(171, signed=False)
    unit_size = integer(172, signed=False)
    bypass_low_temperature = integer(
        173, signed=False, writable=_in_range(10, 30), unit=TEMPERATURE_UNIT
    )
    bypass_comfort_temperature = integer(
        174, signed=False, writable=_in_range(18, 25), unit=TEMPERATURE_UNIT
    )
