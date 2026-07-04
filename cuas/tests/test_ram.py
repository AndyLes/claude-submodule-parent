from cuas.design.ram import kinetic_energy_j, momentum_kgms, arm_first_mode_hz, hover_rotation_hz


def test_ke():
    assert kinetic_energy_j(0.8, 45.0) == 0.5 * 0.8 * 45.0 ** 2


def test_momentum():
    assert momentum_kgms(0.8, 45.0) == 36.0


def test_deeper_arm_higher_frequency():
    shallow = arm_first_mode_hz(7, 7, 95, 32, 1.8e9, 1270)
    deep = arm_first_mode_hz(7, 12, 95, 32, 1.8e9, 1270)
    assert deep > shallow > 0


def test_hover_below_max():
    hz = hover_rotation_hz(32000, 13.2, 1.95)
    assert 0 < hz < 32000 / 60
