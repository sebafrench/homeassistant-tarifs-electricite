"""Local, event-driven electricity time-of-use tariff integration."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXPORT_PRICE, CONF_MODE, CONF_PERIODS, CONF_PRICE_HC, CONF_PRICE_HP,
    CONF_TIMEZONE, DEFAULT_EXPORT_PRICE, DOMAIN, MAX_PRICE, MODE_AUTO,
    MODE_HC, MODE_HP, MODES, PERIOD_HC, PERIOD_HP, PLATFORMS,
    SERVICE_SET_MODE, SERVICE_SET_PRICE_HC, SERVICE_SET_PRICE_HP,
    SIGNAL_UPDATE,
)
from .schedule import (
    TariffValidationError, is_heure_creuse, next_tariff_transition,
    normalize_price, validate_rules,
)

PRICE_SERVICE_SCHEMA = vol.Schema({
    vol.Required("prix"): vol.All(vol.Coerce(float), vol.Range(min=0, max=MAX_PRICE)),
})
MODE_SERVICE_SCHEMA = vol.Schema({
    vol.Required("mode"): vol.In(MODES),
})


class TariffRuntime:
    """Holds current values and one scheduled next-change callback."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.settings: dict = {}
        self.period: str = PERIOD_HP
        self.current_price: float = 0.0
        self.next_change: datetime | None = None
        self._unsubscribe_timer = None
        self.apply_settings()

    @property
    def signal(self) -> str:
        return f"{SIGNAL_UPDATE}_{self.entry.entry_id}"

    @property
    def timezone(self) -> str:
        return self.settings[CONF_TIMEZONE]

    @property
    def mode(self) -> str:
        return self.settings.get(CONF_MODE, MODE_AUTO)

    def price(self, key: str) -> float:
        return float(self.settings[key])

    @callback
    def apply_settings(self) -> None:
        """Synchronize immediately after load or any persisted options update."""
        data = dict(self.entry.data)
        data.update(self.entry.options)
        data.setdefault(CONF_MODE, MODE_AUTO)
        data.setdefault(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE)
        data[CONF_PERIODS] = validate_rules(data.get(CONF_PERIODS, []))
        self.settings = data
        self.refresh()

    @callback
    def refresh(self) -> None:
        """Evaluate tariff and schedule only the next actual state change."""
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
            self._unsubscribe_timer = None

        now_utc = dt_util.utcnow()
        local_now = now_utc.astimezone(ZoneInfo(self.timezone))
        if self.mode == MODE_HP:
            is_hc = False
        elif self.mode == MODE_HC:
            is_hc = True
        else:
            is_hc = is_heure_creuse(self.settings[CONF_PERIODS], local_now)

        self.period = PERIOD_HC if is_hc else PERIOD_HP
        key = CONF_PRICE_HC if is_hc else CONF_PRICE_HP
        self.current_price = self.price(key)
        self.next_change = None

        if self.mode == MODE_AUTO:
            self.next_change = next_tariff_transition(
                self.settings[CONF_PERIODS], self.timezone, now_utc
            )
            if self.next_change is not None:
                self._unsubscribe_timer = async_track_point_in_utc_time(
                    self.hass, self._time_reached, self.next_change
                )
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def _time_reached(self, _now: datetime) -> None:
        """One-shot scheduled callback. Schedule the subsequent boundary."""
        self._unsubscribe_timer = None
        self.refresh()

    @callback
    def update_option(self, key: str, value: object) -> None:
        """Persist an individual change without discarding other options."""
        options = dict(self.entry.options)
        # Older installations can have their initial values only in data.
        options[key] = value
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        # Immediate state update, regardless of listener dispatch scheduling.
        self.apply_settings()

    @callback
    def stop(self) -> None:
        if self._unsubscribe_timer is not None:
            self._unsubscribe_timer()
            self._unsubscribe_timer = None


@callback
def _only_runtime(hass: HomeAssistant) -> TariffRuntime:
    active = hass.data.get(DOMAIN, {})
    if len(active) != 1:
        raise HomeAssistantError(
            "Tarifs Électricité HP/HC doit être configuré et chargé avant cette action."
        )
    return next(iter(active.values()))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register custom actions on domain setup, not per config entry."""
    hass.data.setdefault(DOMAIN, {})

    @callback
    def _set_price_hp(call: ServiceCall) -> None:
        try:
            value = normalize_price(call.data["prix"])
        except TariffValidationError as exc:
            raise HomeAssistantError("Prix HP invalide") from exc
        _only_runtime(hass).update_option(CONF_PRICE_HP, value)

    @callback
    def _set_price_hc(call: ServiceCall) -> None:
        try:
            value = normalize_price(call.data["prix"])
        except TariffValidationError as exc:
            raise HomeAssistantError("Prix HC invalide") from exc
        _only_runtime(hass).update_option(CONF_PRICE_HC, value)

    @callback
    def _set_mode(call: ServiceCall) -> None:
        mode = call.data["mode"]
        if mode not in MODES:
            raise HomeAssistantError("Mode inconnu")
        _only_runtime(hass).update_option(CONF_MODE, mode)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_PRICE_HP, _set_price_hp, schema=PRICE_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PRICE_HC, _set_price_hc, schema=PRICE_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_MODE, _set_mode, schema=MODE_SERVICE_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Instantiate a single local tariff scheduler and its entities."""
    runtime = TariffRuntime(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        runtime.stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply changes without unloading entities or restarting HA."""
    if runtime := hass.data.get(DOMAIN, {}).get(entry.entry_id):
        runtime.apply_settings()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Clean up entities and scheduled callback."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime is not None:
        runtime.stop()
    return True
