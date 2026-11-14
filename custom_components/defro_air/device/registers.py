"""Mapa rejestrów rekuperatora Defro Air (sterownik ST-340 v2).

Źródło: tabela parametrów Modbus z instrukcji „ST-340 v2 Medium DEFRO”
(program 2.1.61), sprawdzona odczytami z centrali z modułem MBP 1.1.4.

Różnice względem instrukcji, potwierdzone na panelu sterownika:
- rejestr 105 to temperatura wywiewu (z pomieszczeń), a 107 to temperatura
  wyrzutni (na zewnątrz); instrukcja podaje je odwrotnie,
- moduł MBP 1.1.4 obsługuje tylko rejestry 100–155; zakres 156–174 zwraca
  wyjątek „illegal data address” i jest dostępny po aktualizacji programu.

Rejestry 126–128 (adres, prędkość i parametry transmisji) celowo nie są
polami: ich zapis zerwałby łączność z urządzeniem.
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
    """Walidator zapisu: przepuść wartość z zakresu, resztę odrzuć."""

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
    """Rejestry 100–155: obecne w każdej wersji programu."""

    register_ranges = ((100, 155),)

    supply_flow = integer(100, signed=False, unit=FLOW_UNIT)
    """Wydatek nawiewu."""
    extract_flow = integer(101, signed=False, unit=FLOW_UNIT)
    """Wydatek wywiewu."""
    supply_gear = integer(102, signed=False)
    """Aktualny bieg wentylatora nawiewu: 0–3, a w trybie urlop 4 (moc minimalna)."""
    extract_gear = integer(103, signed=False)
    """Aktualny bieg wentylatora wywiewu: 0–3, a w trybie urlop 4 (moc minimalna)."""

    outdoor_temperature = _temperature(104)
    """Temperatura czerpni (powietrze z zewnątrz)."""
    extract_temperature = _temperature(105)
    """Temperatura wywiewu (powietrze z pomieszczeń)."""
    supply_temperature = _temperature(106)
    """Temperatura nawiewu (powietrze do pomieszczeń)."""
    exhaust_temperature = _temperature(107)
    """Temperatura wyrzutni (powietrze na zewnątrz)."""
    gwc_temperature = _temperature(108)
    """Temperatura GWC."""
    heater_control_temperature = _temperature(109)
    """Temperatura kontroli nagrzewnicy."""

    schedule_day = integer(110, signed=False)
    """Dzień programu tygodniowego, którego strefy pokazują rejestry 111–120."""
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
    """GWC pracuje."""
    bypass_active = boolean(133)
    """Bypass jest otwarty."""
    secondary_heating_active = boolean(135)
    """Grzanie wtórne pracuje."""
    holiday_active = boolean(137)
    """Tryb urlop jest aktywny."""
    filter_days = integer(138, signed=False)
    """Stan filtrów w dniach."""
    errors = flags(139, ErrorFlags)
    """Aktywne błędy."""

    gwc_enabled = boolean(140, writable=True)
    """Zezwolenie na pracę GWC."""
    bypass_enabled = boolean(141, writable=True)
    """Zezwolenie na pracę bypassu."""
    secondary_heating_enabled = boolean(143)
    """Zezwolenie na grzanie wtórne (instrukcja nie podaje, czy zapisywalne)."""
    holiday_days = integer(
        145, signed=False, writable=_in_range(0, MAX_HOLIDAY_DAYS), unit="d"
    )
    """Tryb urlop: liczba dni, 0 wyłącza. Sprawdzone na centrali."""
    fireplace = integer(146, signed=False, writable=_in_range(0, MAX_FIREPLACE))
    """Funkcja palenisko: czas w sekundach według instrukcji, 0 wyłącza."""
    party = integer(147, signed=False, writable=_in_range(0, MAX_PARTY))
    """Funkcja party: pozostały czas w minutach, 0 wyłącza.

    Sprawdzone na centrali: wentylatory przechodzą na bieg 3, rejestr odlicza
    w dół co minutę, a wartości 1–14 sterownik podnosi do 15.
    """

    digital_input_gear_3 = boolean(149)
    """Wejście cyfrowe wymuszające bieg 3."""
    digital_input_hood = boolean(150)
    """Wejście cyfrowe okapu."""

    clock_date = raw_register(152, writable=True)
    """Data sterownika, zakodowana bitowo (patrz ``codec.decode_date``)."""
    clock_time = raw_register(153, writable=True)
    """Godzina sterownika, zakodowana bitowo (patrz ``codec.decode_time``)."""

    antifreeze_active = boolean(154)
    """Ochrona przed zamarzaniem wymiennika jest aktywna."""
    secondary_heating_temperature = _temperature(155)
    """Temperatura grzania wtórnego."""


class Extended(Component):
    """Rejestry 156–174: tylko w nowszych wersjach programu."""

    register_ranges = ((156, 174),)

    weekly_enabled = boolean(156, writable=True)
    """Sterowanie tygodniowe."""
    target_gear = integer(157, signed=False, writable=_in_range(0, MAX_GEAR))
    """Bieg zadany (0–3)."""
    windows_mode = boolean(158, writable=True)
    """Tryb okna."""
    humidifier_enabled = boolean(159, writable=True)
    """Nawilżacz."""
    humidifier_heater_enabled = boolean(160, writable=True)
    """Nagrzewnica nawilżacza."""

    gear_1_power = integer(161, signed=False, writable=_in_range(1, 100), unit="%")
    gear_2_power = integer(162, signed=False, writable=_in_range(1, 100), unit="%")
    gear_3_power = integer(163, signed=False, writable=_in_range(1, 100), unit="%")
    gear_1_flow = integer(164, signed=False, writable=_in_range(0, 1342), unit=FLOW_UNIT)
    gear_2_flow = integer(165, signed=False, writable=_in_range(0, 1342), unit=FLOW_UNIT)
    gear_3_flow = integer(166, signed=False, writable=_in_range(0, 1342), unit=FLOW_UNIT)

    flow_balancing = boolean(168, writable=True)
    """Stabilizacja przepływu (Flow balancing)."""
    enthalpy_exchanger = boolean(169, writable=True)
    """Wymiennik entalpiczny."""
    filter_runtime = integer(170, signed=False)
    """Czas pracy filtrów."""
    software_version = integer(171, signed=False)
    """Wersja oprogramowania."""
    unit_size = integer(172, signed=False)
    """Rozmiar wybranej centrali."""
    bypass_low_temperature = integer(
        173, signed=False, writable=_in_range(10, 30), unit=TEMPERATURE_UNIT
    )
    """Bypass: dolna temperatura załączenia."""
    bypass_comfort_temperature = integer(
        174, signed=False, writable=_in_range(18, 25), unit=TEMPERATURE_UNIT
    )
    """Bypass: temperatura komfortu."""
