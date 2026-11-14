"""Dodawanie centrali po adresie bramki Modbus TCP."""

from __future__ import annotations

import logging
from typing import Any

from modbus_connection import ModbusError, ModbusTcpParams
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .device import CORE, DefroAir

_LOGGER = logging.getLogger(__name__)

DEFAULT_TITLE = "Defro Air"


def _integer(minimum: int, maximum: int, unit: str | None = None) -> probatio.All:
    config = NumberSelectorConfig(
        mode=NumberSelectorMode.BOX, min=minimum, max=maximum, step=1
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return probatio.All(NumberSelector(config), probatio.Coerce(int))


def _connection_schema(defaults: dict[str, Any]) -> probatio.Schema:
    host = defaults.get(CONF_HOST)
    return probatio.Schema(
        {
            (
                probatio.Required(CONF_HOST, default=host)
                if host is not None
                else probatio.Required(CONF_HOST)
            ): TextSelector(),
            probatio.Required(
                CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
            ): _integer(1, 65535),
            probatio.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            ): _integer(1, 247),
        }
    )


class DefroAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Konfiguracja integracji z interfejsu użytkownika."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DefroAirOptionsFlow:
        return DefroAirOptionsFlow()

    async def _async_probe(self, user_input: dict[str, Any]) -> str | None:
        """Sprawdź, czy pod adresem odpowiada centrala. Zwraca klucz błędu."""
        params = ModbusTcpParams(host=user_input[CONF_HOST], port=user_input[CONF_PORT])
        try:
            async with async_get_temporary_unit(
                self.hass, params, user_input[CONF_UNIT_ID]
            ) as unit:
                report = await DefroAir(unit).async_update()
        except (ModbusError, HomeAssistantError) as err:
            _LOGGER.debug("Brak połączenia z centralą: %r", err)
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Nieoczekiwany błąd przy sprawdzaniu połączenia")
            return "unknown"
        if CORE not in report.updated:
            # Coś odpowiada, ale nie udostępnia rejestrów 100–155.
            _LOGGER.debug("Urządzenie odrzuciło odczyt: %r", report.failed)
            return "unsupported_device"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zapytaj o adres i sprawdź, czy centrala odpowiada."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                }
            )
            if (error := await self._async_probe(user_input)) is None:
                return self.async_create_entry(title=DEFAULT_TITLE, data=user_input)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Zmień adres istniejącej centrali (np. po zmianie IP bramki)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            if (error := await self._async_probe(user_input)) is None:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(user_input or dict(entry.data)),
            errors=errors,
        )


class DefroAirOptionsFlow(OptionsFlowWithReload):
    """Opcje: częstotliwość odczytu."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): _integer(MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL, "s"),
                }
            ),
        )
