"""Odczyt z prawdziwej centrali, bez Home Assistanta (tylko odczyt, nic nie zapisuje).

Użycie:  python tools/live_read.py HOST [PORT] [UNIT_ID] [--raw]
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

# Warstwa urządzenia nie zależy od Home Assistanta, więc ładujemy ją wprost,
# z pominięciem __init__.py integracji.
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "defro_air"))

from device import DefroAir  # noqa: E402
from modbus_connection import ModbusTcpParams  # noqa: E402
from modbus_connection.tmodbus import ModbusConnection  # noqa: E402


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raw = "--raw" in sys.argv
    if not args:
        print(__doc__)
        return 2
    host = args[0]
    port = int(args[1]) if len(args) > 1 else 502
    unit_id = int(args[2]) if len(args) > 2 else 1

    connection = ModbusConnection(ModbusTcpParams(host=host, port=port))
    try:
        device = DefroAir(connection.for_unit(unit_id))
        report = await device.async_update()
        print(f"podsystemy: {device.components}")
        print(f"odczytane: {sorted(report.updated)}  błędy: {report.failed}")

        core = device.core
        for name in core.declared_fields:
            print(f"  core.{name} = {getattr(core, name)!r}")
        if device.extended is not None:
            for name in device.extended.declared_fields:
                print(f"  extended.{name} = {getattr(device.extended, name)!r}")
        print("pochodne:")
        for name in (
            "outdoor_temperature",
            "extract_temperature",
            "supply_temperature",
            "exhaust_temperature",
            "gwc_temperature",
            "heater_control_temperature",
            "secondary_heating_temperature",
            "efficiency",
            "recovered_power",
            "has_error",
            "error_keys",
            "clock",
        ):
            print(f"  {name} = {getattr(device, name)!r}")
        if raw:
            print(json.dumps(await device.async_read_all_raw(), indent=1))
    finally:
        await connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
