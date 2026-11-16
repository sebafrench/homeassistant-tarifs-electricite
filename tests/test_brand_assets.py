"""Vérifie les fichiers d'identité visuelle sans dépendances externes."""
import struct
from pathlib import Path

BRAND = Path(__file__).resolve().parents[1] / "custom_components/tarifs_electricite/brand"

def _assert_png_size(filename, expected):
    data = (BRAND / filename).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    assert struct.unpack(">II", data[16:24]) == (expected, expected)

def test_icon_256():
    _assert_png_size("icon.png", 256)

def test_icon_512():
    _assert_png_size("icon@2x.png", 512)