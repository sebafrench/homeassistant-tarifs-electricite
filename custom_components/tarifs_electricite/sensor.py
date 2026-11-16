"""Native Home Assistant sensors for electricity prices and periods."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DAYS, CONF_END, CONF_EXPORT_PRICE, CONF_PERIODS,
    CONF_PRICE_HC, CONF_PRICE_HP, CONF_START, DOMAIN, WEEKDAYS_FR,
    CONF_SATURDAY_FULL_DAY, CONF_SUNDAY_FULL_DAY,
)
from . import TariffRuntime


SENSOR_DESCRIPTORS: dict[str, tuple[str, str]] = {
    "current": ("Tarif électricité actuel", "mdi:currency-eur"),
    "period": ("Période tarifaire", "mdi:clock-outline"),
    "next": ("Prochain changement tarif", "mdi:clock-fast"),
    "hp": ("Prix kWh heures pleines", "mdi:currency-eur"),
    "hc": ("Prix kWh heures creuses", "mdi:currency-eur"),
    "schedule": ("Horaires heures creuses", "mdi:calendar-clock"),
    "export": ("Prix revente surplus", "mdi:solar-power"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime: TariffRuntime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TariffSensor(runtime, key) for key in SENSOR_DESCRIPTORS])


class TariffSensor(SensorEntity):
    """Push-only tariff sensor; the runtime is the source of truth."""

    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(self, runtime: TariffRuntime, key: str) -> None:
        self.runtime = runtime
        self.key = key
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_name, self._attr_icon = SENSOR_DESCRIPTORS[key]
        if key == "next":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key in ("current", "hp", "hc", "export"):
            self._attr_native_unit_of_measurement = "EUR/kWh"

    @property
    def native_value(self) -> Any:
        if self.key == "current":
            return self.runtime.current_price
        if self.key == "period":
            return self.runtime.period
        if self.key == "next":
            return self.runtime.next_change
        if self.key == "hp":
            return self.runtime.price(CONF_PRICE_HP)
        if self.key == "hc":
            return self.runtime.price(CONF_PRICE_HC)
        if self.key == "export":
            return self.runtime.price(CONF_EXPORT_PRICE)
        total = len(self.runtime.settings[CONF_PERIODS])
        days = len(self.runtime.full_day_hc)
        return f"{total} plages · {days} jours 24 h HC" if days else f"{total} plages"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.key == "schedule":
            return {
                "fuseau_horaire": self.runtime.timezone,
                "samedi_24h_hc": self.runtime.settings.get(CONF_SATURDAY_FULL_DAY, False),
                "dimanche_24h_hc": self.runtime.settings.get(CONF_SUNDAY_FULL_DAY, False),
                "jours_entiers_hc": [WEEKDAYS_FR[day] for day in sorted(self.runtime.full_day_hc)],
                "plages": [
                    {
                        "debut": rule[CONF_START],
                        "fin": rule[CONF_END],
                        "jours": ", ".join(WEEKDAYS_FR[day] for day in rule[CONF_DAYS]),
                        "traverse_minuit": rule[CONF_END] < rule[CONF_START],
                    }
                    for rule in self.runtime.settings[CONF_PERIODS]
                ],
            }
        if self.key == "current":
            return {"periode": self.runtime.period, "mode": self.runtime.mode}
        return None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.runtime.signal, self._async_state_changed
        ))

    @callback
    def _async_state_changed(self) -> None:
        self.async_write_ha_state()
