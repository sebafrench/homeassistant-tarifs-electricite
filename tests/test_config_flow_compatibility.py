"""Regression tests: price form must honor Home Assistant selector minimum step."""
from pathlib import Path
import ast

FLOW = Path(__file__).resolve().parents[1] / "custom_components" / "tarifs_electricite" / "config_flow.py"


def test_price_selectors_use_allowed_step():
    """Home Assistant NumberSelector requires numeric steps >=0.001; any is valid."""
    tree = ast.parse(FLOW.read_text(encoding="utf-8"))
    steps = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "NumberSelectorConfig":
            step = next((kw.value for kw in node.keywords if kw.arg == "step"), None)
            assert step is not None, "Every price number selector needs an explicit step"
            steps.append(ast.literal_eval(step))
    assert steps == ["any", "any", "any"]
