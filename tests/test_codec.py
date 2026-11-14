"""Dekodowanie wartości: data, godzina, błędy, sprawność."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from custom_components.defro_air.device.codec import (
    ErrorFlags,
    decode_clock,
    decode_date,
    decode_time,
    encode_date,
    encode_time,
    error_keys,
    heat_recovery_efficiency,
    plausible_temperature,
    recovered_power,
)


def test_date_example_from_manual() -> None:
    # Instrukcja: 31.01.2022 → 11111 0001 0010110.
    raw = 0b1111100010010110
    assert decode_date(raw) == date(2022, 1, 31)
    assert encode_date(date(2022, 1, 31)) == raw


def test_time_example_from_manual() -> None:
    # Instrukcja: 01:30 → 00000001 00011110.
    raw = 0b0000000100011110
    assert decode_time(raw) == time(1, 30)
    assert encode_time(time(1, 30)) == raw


def test_clock_read_from_real_unit() -> None:
    assert decode_clock(30106, 4112) == datetime(2026, 11, 14, 16, 16)


@pytest.mark.parametrize("raw", [0, 0xFFFF, (31 << 11) | (2 << 7) | 26])
def test_invalid_date_is_none(raw: int) -> None:
    assert decode_date(raw) is None


def test_invalid_time_is_none() -> None:
    assert decode_time((25 << 8) | 0) is None
    assert decode_time((10 << 8) | 61) is None
    assert decode_clock(None, 4112) is None


def test_date_out_of_controller_range() -> None:
    with pytest.raises(ValueError):
        encode_date(date(2128, 1, 1))


def test_error_keys() -> None:
    assert error_keys(None) is None
    assert error_keys(0) == []
    flags = ErrorFlags.EXHAUST_FAN | ErrorFlags.OUTDOOR_SENSOR | ErrorFlags.CONTROL_SENSOR
    assert error_keys(flags) == ["exhaust_fan", "outdoor_sensor", "control_sensor"]


def test_unknown_error_bits_are_reported() -> None:
    assert error_keys((1 << 6) | (1 << 15) | 1) == [
        "exhaust_fan",
        "unknown_bit_6",
        "unknown_bit_15",
    ]


def test_plausible_temperature() -> None:
    assert plausible_temperature(21.400000000000002) == 21.4
    assert plausible_temperature(-4.6) == -4.6
    assert plausible_temperature(171.5) is None
    assert plausible_temperature(-60.0) is None
    assert plausible_temperature(None) is None


def test_efficiency_from_real_unit() -> None:
    # czerpnia 6,2; nawiew 19,4; wywiew 21,4 → (19,4−6,2)/(21,4−6,2) = 86,8 %
    assert heat_recovery_efficiency(6.2, 19.4, 21.4, bypass_active=False) == 86.8


def test_efficiency_unavailable() -> None:
    assert heat_recovery_efficiency(6.2, 19.4, 21.4, bypass_active=True) is None
    assert heat_recovery_efficiency(None, 19.4, 21.4, bypass_active=False) is None
    # Za mała różnica temperatur między wywiewem a czerpnią.
    assert heat_recovery_efficiency(20.0, 20.5, 21.0, bypass_active=False) is None


def test_efficiency_is_clamped() -> None:
    assert heat_recovery_efficiency(0.0, 25.0, 20.0, bypass_active=False) == 100.0
    assert heat_recovery_efficiency(0.0, -1.0, 20.0, bypass_active=False) == 0.0


def test_recovered_power() -> None:
    # 78 m³/h · 0,335 Wh/(m³·K) · (19,4 − 6,2) K = 344,9 W
    assert recovered_power(6.2, 19.4, 78, bypass_active=False) == 345
    # Latem wymiennik chłodzi powietrze nawiewane: wynik ujemny.
    assert recovered_power(30.0, 26.0, 100, bypass_active=False) == -134
    assert recovered_power(6.2, 19.4, 78, bypass_active=True) is None
    assert recovered_power(6.2, 19.4, None, bypass_active=False) is None
