from cuas.design.mass import auw_g, center_of_mass_mm
from cuas.design.e2_config import COMPONENTS

_C = [
    {"name": "a", "mass_g": 100, "x_mm": 10, "y_mm": 0, "z_mm": 0},
    {"name": "b", "mass_g": 100, "x_mm": -10, "y_mm": 0, "z_mm": 0},
]


def test_auw_sums():
    assert auw_g(_C) == 200


def test_com_balanced_is_center():
    cx, cy, cz = center_of_mass_mm(_C)
    assert abs(cx) < 1e-9 and abs(cy) < 1e-9


def test_real_config_auw_in_range():
    assert 650 <= auw_g(COMPONENTS) <= 900
