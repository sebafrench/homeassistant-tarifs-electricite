"""UI setup and options wizards for Tarifs Électricité HP/HC."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DAYS, CONF_END, CONF_EXPORT_PRICE, CONF_MODE, CONF_PERIOD_INDEX,
    CONF_PERIODS, CONF_PRICE_HC, CONF_PRICE_HP, CONF_START, CONF_TIMEZONE,
    CONF_SATURDAY_FULL_DAY, CONF_SUNDAY_FULL_DAY,
    DEFAULT_EXPORT_PRICE, DEFAULT_PRICE_HC, DEFAULT_PRICE_HP, DOMAIN,
    MAX_PRICE, MAX_RULES, MODE_AUTO, NAME, WEEKDAYS_FR,
)
from .schedule import (
    TariffValidationError, normalize_clock, normalize_price, normalize_timezone,
    validate_rules,
)


def _price_schema(current: dict) -> vol.Schema:
    """Form schema; use arbitrary precision (HA number selector min step is 0.001)."""
    return vol.Schema(
        {
            vol.Required(CONF_PRICE_HP, default=float(current.get(CONF_PRICE_HP, DEFAULT_PRICE_HP))):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=0, max=MAX_PRICE, step="any",
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="EUR/kWh",
                )),
            vol.Required(CONF_PRICE_HC, default=float(current.get(CONF_PRICE_HC, DEFAULT_PRICE_HC))):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=0, max=MAX_PRICE, step="any",
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="EUR/kWh",
                )),
            vol.Required(CONF_EXPORT_PRICE, default=float(current.get(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE))):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=0, max=MAX_PRICE, step="any",
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="EUR/kWh",
                )),
            vol.Required(CONF_TIMEZONE, default=current.get(CONF_TIMEZONE, "Europe/Paris")):
                selector.TextSelector(),
        }
    )


def _weekend_schema(current: dict) -> vol.Schema:
    """Two independent switches for Saturday and Sunday, 00:00-24:00 local."""
    return vol.Schema({
        vol.Required(CONF_SATURDAY_FULL_DAY, default=current.get(CONF_SATURDAY_FULL_DAY, False)):
            selector.BooleanSelector(),
        vol.Required(CONF_SUNDAY_FULL_DAY, default=current.get(CONF_SUNDAY_FULL_DAY, False)):
            selector.BooleanSelector(),
    })


def _rule_schema(rule: dict | None = None) -> vol.Schema:
    """One user-editable time interval. Weekdays refer to the start day."""
    rule = rule or {}
    return vol.Schema(
        {
            vol.Required(CONF_START, default=f"{rule.get(CONF_START, '22:30')}:00"):
                selector.TimeSelector(),
            vol.Required(CONF_END, default=f"{rule.get(CONF_END, '06:30')}:00"):
                selector.TimeSelector(),
            vol.Required(CONF_DAYS, default=[str(x) for x in rule.get(CONF_DAYS, range(7))]):
                selector.SelectSelector(selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=str(i), label=day)
                             for i, day in enumerate(WEEKDAYS_FR)],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )),
        }
    )


def _short_label(rule: dict, index: int) -> str:
    day_names = ", ".join(WEEKDAYS_FR[day][:3] for day in rule[CONF_DAYS])
    return f"{index + 1}. {rule[CONF_START]}–{rule[CONF_END]} ({day_names})"


def _index_schema(rules: list[dict]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_PERIOD_INDEX): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[selector.SelectOptionDict(value=str(i), label=_short_label(rule, i))
                         for i, rule in enumerate(rules)],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    })


class ScheduleWizard:
    """Reusable wizard steps for the installation and options flows."""

    _draft: dict[str, Any]
    _editing_index: int

    def _validate_prices(self, user_input: dict) -> dict:
        return {
            CONF_PRICE_HP: normalize_price(user_input[CONF_PRICE_HP]),
            CONF_PRICE_HC: normalize_price(user_input[CONF_PRICE_HC]),
            CONF_EXPORT_PRICE: normalize_price(user_input[CONF_EXPORT_PRICE]),
            CONF_TIMEZONE: normalize_timezone(user_input[CONF_TIMEZONE]),
        }

    async def async_step_schedule(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Menu to add, edit and delete any of up to four starts per day."""
        options = ["prices", "weekend"]
        if len(self._draft[CONF_PERIODS]) < MAX_RULES:
            options.append("add_period")
        if self._draft[CONF_PERIODS]:
            options.extend(["edit_period", "remove_period"])
        options.append("finish")
        return self.async_show_menu(step_id="schedule", menu_options=options)

    async def async_step_prices(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._draft.update(self._validate_prices(user_input))
            except TariffValidationError as exc:
                errors["base"] = str(exc)
            else:
                return await self.async_step_schedule()
        return self.async_show_form(
            step_id="prices", data_schema=_price_schema(self._draft), errors=errors
        )

    async def async_step_weekend(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Allow a full Saturday and/or Sunday without creating timed rules."""
        if user_input is not None:
            self._draft[CONF_SATURDAY_FULL_DAY] = user_input[CONF_SATURDAY_FULL_DAY]
            self._draft[CONF_SUNDAY_FULL_DAY] = user_input[CONF_SUNDAY_FULL_DAY]
            return await self.async_step_schedule()
        return self.async_show_form(
            step_id="weekend", data_schema=_weekend_schema(self._draft)
        )

    async def async_step_add_period(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                new_rule = {
                    CONF_START: normalize_clock(user_input[CONF_START]),
                    CONF_END: normalize_clock(user_input[CONF_END]),
                    CONF_DAYS: user_input[CONF_DAYS],
                }
                validated = validate_rules([*self._draft[CONF_PERIODS], new_rule])
            except TariffValidationError as exc:
                errors["base"] = str(exc)
            else:
                self._draft[CONF_PERIODS] = validated
                return await self.async_step_schedule()
        return self.async_show_form(
            step_id="add_period", data_schema=_rule_schema(), errors=errors
        )

    async def async_step_edit_period(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._editing_index = int(user_input[CONF_PERIOD_INDEX])
            return await self.async_step_change_period()
        return self.async_show_form(
            step_id="edit_period", data_schema=_index_schema(self._draft[CONF_PERIODS])
        )

    async def async_step_change_period(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                candidate = deepcopy(self._draft[CONF_PERIODS])
                candidate[self._editing_index] = {
                    CONF_START: normalize_clock(user_input[CONF_START]),
                    CONF_END: normalize_clock(user_input[CONF_END]),
                    CONF_DAYS: user_input[CONF_DAYS],
                }
                validated = validate_rules(candidate)
            except TariffValidationError as exc:
                errors["base"] = str(exc)
            else:
                self._draft[CONF_PERIODS] = validated
                return await self.async_step_schedule()
        return self.async_show_form(
            step_id="change_period",
            data_schema=_rule_schema(self._draft[CONF_PERIODS][self._editing_index]),
            errors=errors,
        )

    async def async_step_remove_period(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            index = int(user_input[CONF_PERIOD_INDEX])
            self._draft[CONF_PERIODS].pop(index)
            return await self.async_step_schedule()
        return self.async_show_form(
            step_id="remove_period", data_schema=_index_schema(self._draft[CONF_PERIODS])
        )


class TarifsElectriciteConfigFlow(ScheduleWizard, config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a single instance of the local tariff manager."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                prices = self._validate_prices(user_input)
            except TariffValidationError as exc:
                errors["base"] = str(exc)
            else:
                self._draft = {
                    **prices,
                    CONF_PERIODS: [],
                    CONF_MODE: MODE_AUTO,
                    CONF_SATURDAY_FULL_DAY: False,
                    CONF_SUNDAY_FULL_DAY: False,
                }
                return await self.async_step_schedule()
        return self.async_show_form(
            step_id="user",
            data_schema=_price_schema({CONF_TIMEZONE: self.hass.config.time_zone or "Europe/Paris"}),
            errors=errors,
        )

    async def async_step_finish(self, user_input: dict | None = None) -> ConfigFlowResult:
        try:
            self._draft[CONF_PERIODS] = validate_rules(self._draft[CONF_PERIODS])
        except TariffValidationError:
            return await self.async_step_schedule()
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=NAME, data=self._draft)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return TarifsElectriciteOptionsFlow()


class TarifsElectriciteOptionsFlow(ScheduleWizard, config_entries.OptionsFlow):
    """Edit draft options, then apply all edits without HA restart."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        self._draft = deepcopy(dict(self.config_entry.data))
        self._draft.update(deepcopy(dict(self.config_entry.options)))
        self._draft.setdefault(CONF_PERIODS, [])
        self._draft.setdefault(CONF_MODE, MODE_AUTO)
        self._draft.setdefault(CONF_EXPORT_PRICE, DEFAULT_EXPORT_PRICE)
        self._draft.setdefault(CONF_SATURDAY_FULL_DAY, False)
        self._draft.setdefault(CONF_SUNDAY_FULL_DAY, False)
        self._draft.setdefault(CONF_TIMEZONE, self.hass.config.time_zone or "Europe/Paris")
        return await self.async_step_schedule()

    async def async_step_finish(self, user_input: dict | None = None) -> ConfigFlowResult:
        try:
            self._draft[CONF_PERIODS] = validate_rules(self._draft[CONF_PERIODS])
        except TariffValidationError:
            return await self.async_step_schedule()
        # The select or service may have updated the mode while this wizard
        # was open; preserve the current persisted mode rather than overwriting it.
        self._draft[CONF_MODE] = self.config_entry.options.get(
            CONF_MODE, self.config_entry.data.get(CONF_MODE, MODE_AUTO)
        )
        return self.async_create_entry(title="", data=self._draft)
