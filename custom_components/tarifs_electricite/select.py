"""Persisted tariff mode selection."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TariffRuntime
from .const import CONF_MODE, DOMAIN, MODE_BY_LABEL, MODE_LABELS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: TariffRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TariffModeSelect(runtime)])


class TariffModeSelect(SelectEntity):
    """Select auto or forced mode; do not reset on startup."""

    _attr_name = "Mode tarifaire"
    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_icon = "mdi:swap-horizontal"
    _attr_options = list(MODE_LABELS.values())

    def __init__(self, runtime: TariffRuntime) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_mode"

    @property
    def current_option(self) -> str:
        return MODE_LABELS[self.runtime.mode]

    async def async_select_option(self, option: str) -> None:
        self.runtime.update_option(CONF_MODE, MODE_BY_LABEL[option])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.runtime.signal, self._async_state_changed
        ))

    @callback
    def _async_state_changed(self) -> None:
        self.async_write_ha_state()
