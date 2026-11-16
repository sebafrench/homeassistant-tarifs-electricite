"""Constants for the local HP/HC electricity tariff integration."""

DOMAIN = "tarifs_electricite"
NAME = "Tarifs Électricité HP/HC"

CONF_PRICE_HP = "price_hp"
CONF_PRICE_HC = "price_hc"
CONF_EXPORT_PRICE = "export_price"
CONF_TIMEZONE = "timezone"
CONF_PERIODS = "periods"
CONF_START = "start"
CONF_END = "end"
CONF_DAYS = "days"
CONF_MODE = "mode"
CONF_PERIOD_INDEX = "period_index"
CONF_SATURDAY_FULL_DAY = "saturday_full_day_hc"
CONF_SUNDAY_FULL_DAY = "sunday_full_day_hc"

MODE_AUTO = "automatique"
MODE_HP = "hp_force"
MODE_HC = "hc_force"
MODES = (MODE_AUTO, MODE_HP, MODE_HC)
MODE_LABELS = {
    MODE_AUTO: "Automatique",
    MODE_HP: "HP forcé",
    MODE_HC: "HC forcé",
}
MODE_BY_LABEL = {label: mode for mode, label in MODE_LABELS.items()}

PERIOD_HP = "Heures Pleines"
PERIOD_HC = "Heures Creuses"

DEFAULT_PRICE_HP = "0.2500"
DEFAULT_PRICE_HC = "0.1900"
DEFAULT_EXPORT_PRICE = "0.0000"
MAX_PRICE = 10
MAX_RULES = 28
MAX_DAILY_RULES = 4

WEEKDAYS_FR = (
    "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"
)
PLATFORMS = ("sensor", "number", "select")

SIGNAL_UPDATE = f"{DOMAIN}_update"
SERVICE_SET_PRICE_HP = "set_prix_hp"
SERVICE_SET_PRICE_HC = "set_prix_hc"
SERVICE_SET_MODE = "set_mode"
