"""Static regression for required HA flow and translations (HA not installed in CI)."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "tarifs_electricite"


def test_config_and_options_wizards_show_independent_weekend_toggles():
    tree = ast.parse((INTEGRATION / "config_flow.py").read_text())
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}
    assert "async_step_weekend" in methods
    flow = (INTEGRATION / "config_flow.py").read_text()
    assert 'options = ["prices", "weekend"]' in flow
    assert "selector.BooleanSelector()" in flow
    assert "CONF_SATURDAY_FULL_DAY" in flow and "CONF_SUNDAY_FULL_DAY" in flow
    assert "self._draft.setdefault(CONF_SATURDAY_FULL_DAY, False)" in flow
    assert "self._draft.setdefault(CONF_SUNDAY_FULL_DAY, False)" in flow


def test_fr_en_translation_keys_and_version():
    for name in ("strings.json", "translations/fr.json", "translations/en.json"):
        obj = json.loads((INTEGRATION / name).read_text(encoding="utf-8"))
        for section in ("config", "options"):
            assert "weekend" in obj[section]["step"]["schedule"]["menu_options"]
            assert set(obj[section]["step"]["weekend"]["data"]) == {
                "saturday_full_day_hc", "sunday_full_day_hc"
            }
    assert json.loads((INTEGRATION / "manifest.json").read_text())["version"] == "1.0.2"
