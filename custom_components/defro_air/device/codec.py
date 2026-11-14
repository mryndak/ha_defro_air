"""Kodowanie wartości złożonych i wartości wyliczane."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import IntFlag

# Brak czujnika: 63066 według instrukcji, 1715 w module MBP 1.1.4.
TEMPERATURE_UNAVAILABLE = (63066, 1715)

TEMPERATURE_MIN = -50.0
TEMPERATURE_MAX = 100.0
AIR_HEAT_CAPACITY = 0.335  # Wh/(m³·K)
MIN_EFFICIENCY_DELTA = 2.0


class ErrorFlags(IntFlag):
    """Rejestr 139."""

    EXHAUST_FAN = 1 << 0
    SUPPLY_FAN = 1 << 1
    OUTDOOR_SENSOR = 1 << 2
    EXTRACT_SENSOR = 1 << 3
    SUPPLY_SENSOR = 1 << 4
    EXHAUST_SENSOR = 1 << 5
    OUTDOOR_SENSOR_2 = 1 << 7
    SUPPLY_SENSOR_2 = 1 << 8
    EXHAUST_PRESSURE_SENSOR = 1 << 9
    SUPPLY_PRESSURE_SENSOR = 1 << 10
    HUMIDIFIER_SENSOR = 1 << 11
    HUMIDIFIER_SENSOR_2 = 1 << 12
    CONTROL_SENSOR = 1 << 13


def error_keys(flags: int | None) -> list[str] | None:
    if flags is None:
        return None
    value = int(flags)
    keys: list[str] = []
    for bit in range(16):
        mask = 1 << bit
        if not value & mask:
            continue
        try:
            name = ErrorFlags(mask).name
        except ValueError:
            name = None
        keys.append(name.lower() if name else f"unknown_bit_{bit}")
    return keys


def plausible_temperature(value: float | None) -> float | None:
    if value is None or not TEMPERATURE_MIN <= value <= TEMPERATURE_MAX:
        return None
    return round(value, 1)


# Rejestr 152: dzień << 11 | miesiąc << 7 | rok - 2000
def decode_date(raw: int | None) -> date | None:
    if raw is None:
        return None
    try:
        return date(2000 + (raw & 0x7F), (raw >> 7) & 0x0F, (raw >> 11) & 0x1F)
    except ValueError:
        return None


def encode_date(value: date) -> int:
    if not 2000 <= value.year <= 2127:
        raise ValueError(f"rok poza zakresem sterownika: {value.year}")
    return (value.day << 11) | (value.month << 7) | (value.year - 2000)


# Rejestr 153: godzina << 8 | minuta
def decode_time(raw: int | None) -> time | None:
    if raw is None:
        return None
    try:
        return time((raw >> 8) & 0xFF, raw & 0xFF)
    except ValueError:
        return None


def encode_time(value: time) -> int:
    return (value.hour << 8) | value.minute


def decode_clock(raw_date: int | None, raw_time: int | None) -> datetime | None:
    day = decode_date(raw_date)
    clock = decode_time(raw_time)
    if day is None or clock is None:
        return None
    return datetime.combine(day, clock)


def heat_recovery_efficiency(
    outdoor: float | None,
    supply: float | None,
    extract: float | None,
    *,
    bypass_active: bool | None,
) -> float | None:
    """(nawiew − czerpnia) / (wywiew − czerpnia), w procentach."""
    if outdoor is None or supply is None or extract is None or bypass_active:
        return None
    delta = extract - outdoor
    if abs(delta) < MIN_EFFICIENCY_DELTA:
        return None
    efficiency = (supply - outdoor) / delta * 100
    return round(min(max(efficiency, 0.0), 100.0), 1)


def recovered_power(
    outdoor: float | None,
    supply: float | None,
    supply_flow: int | None,
    *,
    bypass_active: bool | None,
) -> float | None:
    """W watach; ujemna, gdy wymiennik chłodzi nawiew."""
    if outdoor is None or supply is None or supply_flow is None or bypass_active:
        return None
    return round(supply_flow * AIR_HEAT_CAPACITY * (supply - outdoor))
