"""Box-editable prices for the local tariff manager."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TariffRuntime
from .const import (
    CONF_EXPORT_PRICE, CONF_PRICE_HC, CONF_PRICE_HP, DOMAIN, MAX_PRICE,
)
from .schedule import normalize_price

PRICE_ENTITIES = {
    CONF_PRICE_HP: ("Tarif HP", "mdi:currency-eur"),
    CONF_PRICE_HC: ("Tarif HC", "mdi:currency-eur"),
    CONF_EXPORT_PRICE: ("Tarif revente surplus", "mdi:solar-power"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: TariffRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TariffNumber(runtime, key) for key in PRICE_ENTITIES])


class TariffNumber(NumberEntity):
    """Editable price with four decimal places, persisted in entry options."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_native_min_value = 0.0
    _attr_native_max_value = float(MAX_PRICE)
    _attr_native_step = 0.0001
    _attr_native_unit_of_measurement = "EUR/kWh"
    _attr_mode = NumberMode.BOX

    def __init__(self, runtime: TariffRuntime, key: str) -> None:
        self.runtime = runtime
        self.key = key
        self._attr_unique_id = f"{runtime.entry.entry_id}_number_{key}"
        self._attr_name, self._attr_icon = PRICE_ENTITIES[key]

    @property
    def native_value(self) -> float:
        return self.runtime.price(self.key)

    async def async_set_native_value(self, value: float) -> None:
        self.runtime.update_option(self.key, normalize_price(value))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.runtime.signal, self._async_state_changed
        ))

    @callback
    def _async_state_changed(self) -> None:
        self.async_write_ha_state()
