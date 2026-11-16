"""Import the pure tariff engine without requiring Home Assistant in test env."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="session")
def engine():
    package = ModuleType("_tariff_schedule_tests")
    package.__path__ = [str(Path(__file__).resolve().parents[1] /
                            "custom_components" / "tarifs_electricite")]
    sys.modules[package.__name__] = package
    return importlib.import_module(f"{package.__name__}.schedule")
