from cuas.design.launch import (launch_energy_j, required_force_n, launch_accel_g,
                                pneumatic_pressure_bar, bungee_peak_g, exit_speed_ms,
                                wing_deploy_margin_ok)

# honest compact-munition numbers: AUW ~1.103 kg, stall ~19.86 m/s, exit ~27.8 m/s (1.4x, folding wing)
_M, _V, _L = 1.103, 27.8, 1.8


def test_energy():
    assert abs(launch_energy_j(_M, _V) - 0.5 * _M * _V ** 2) < 1e-6


def test_force_and_accel_consistent():
    f = required_force_n(_M, _V, _L)
    assert abs(exit_speed_ms(f, _L, _M) - _V) < 1e-6              # оборотність
    assert 15 < launch_accel_g(_V, _L) < 25                       # ~20 g на 1.6 м (ОСЬОВЕ, крила складені)


def test_pneumatic_pressure_low_even_big_bore():
    f = required_force_n(_M, _V, _L)
    assert pneumatic_pressure_bar(f, 130) < 1.0                   # 130мм повнопрохідний поршень -> низький тиск


def test_bungee_peaks_higher():
    assert bungee_peak_g(launch_accel_g(_V, _L)) > launch_accel_g(_V, _L)


def test_deploy_margin():
    assert wing_deploy_margin_ok(27.8, 19.86) is True            # 1.4x зрив — запас для розкриття крила
    assert wing_deploy_margin_ok(20.0, 19.86) is False
