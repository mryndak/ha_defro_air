"""Cykliczny odczyt centrali i reakcja na brak odpowiedzi."""

from __future__ import annotations

from datetime import timedelta
import logging

from modbus_connection import ModbusError, ModbusTimeoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .device import DefroAir, UpdateReport

_LOGGER = logging.getLogger(__name__)

# Po tylu kolejnych timeoutach uznajemy łącze za martwe i otwieramy je na nowo.
TIMEOUTS_BEFORE_RECONNECT = 3

type DefroAirConfigEntry = ConfigEntry[DefroAirCoordinator]


class DefroAirCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Odpytuje centralę i przechowuje informację, co udało się odczytać."""

    config_entry: DefroAirConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: DefroAirConfigEntry, device: DefroAir
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.device = device
        self._timeouts = 0
        self._failed: set[str] = set()

    @property
    def device_info(self) -> DeviceInfo:
        """Jedno urządzenie, do którego należą wszystkie encje wpisu."""
        extended = self.device.extended
        version = extended.software_version if extended is not None else None
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            name=self.config_entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=None if version is None else str(version),
        )

    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
        except ModbusTimeoutError as err:
            self._timeouts += 1
            if self._timeouts >= TIMEOUTS_BEFORE_RECONNECT:
                # Bramka potrafi trzymać otwarte gniazdo, przez które nic już
                # nie przechodzi. Rozłączenie wymusza nowe połączenie.
                self._timeouts = 0
                await self.device.modbus_unit.disconnect()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err) or "timeout"},
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

        self._timeouts = 0
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
                translation_placeholders={"name": self.name},
            ) from ExceptionGroup(
                "żaden podsystem nie odpowiedział", list(report.failed.values())
            )

        self._log_component_changes(report)
        return report

    def _log_component_changes(self, report: UpdateReport) -> None:
        """Zapisz w logu pierwszą awarię podsystemu i jego powrót, bez powtórzeń."""
        failed = set(report.failed)
        for name in failed - self._failed:
            _LOGGER.warning(
                "%s: nie udało się odczytać podsystemu %s: %s",
                self.name,
                name,
                report.failed[name],
            )
        for name in self._failed - failed:
            _LOGGER.info("%s: podsystem %s znów odpowiada", self.name, name)
        self._failed = failed
