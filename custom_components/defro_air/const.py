"""Stałe integracji Defro Air."""

from __future__ import annotations

DOMAIN = "defro_air"

CONF_UNIT_ID = "unit_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 15
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 600

MANUFACTURER = "Defro"
MODEL = "Defro Air (ST-340 v2)"
