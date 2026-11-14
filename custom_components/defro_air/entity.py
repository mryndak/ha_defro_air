"""Wspólna część wszystkich encji Defro Air."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass

from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DefroAirCoordinator
from .device import CORE, DefroAir


@dataclass(frozen=True, kw_only=True)
class DefroAirEntityDescription(EntityDescription):
    """Z którego podsystemu centrali encja czyta dane."""

    component: str = CORE


class DefroAirEntity(CoordinatorEntity[DefroAirCoordinator]):
    """Dostępna, gdy odpowiedział jej podsystem rejestrów."""

    _attr_has_entity_name = True
    entity_description: DefroAirEntityDescription

    def __init__(
        self,
        coordinator: DefroAirCoordinator,
        description: DefroAirEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def device(self) -> DefroAir:
        return self.coordinator.device

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.entity_description.component in self.coordinator.data.updated
        )

    async def _async_write(self, write: Awaitable[None]) -> None:
        try:
            await write
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value",
                translation_placeholders={"error": str(err)},
            ) from err
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err
        # async_request_refresh z debounce zostawiał stary stan
        await self.coordinator.async_refresh()


def served(coordinator: DefroAirCoordinator, descriptions):
    """Opisy encji, których podsystem ta centrala obsługuje."""
    components = coordinator.device.components
    return [d for d in descriptions if d.component in components]
