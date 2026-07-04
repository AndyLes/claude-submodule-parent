from cuas.design.launch import (launch_energy_j, required_force_n, launch_accel_g,
                                pneumatic_pressure_bar, bungee_peak_g, exit_speed_ms,
                                wing_deploy_margin_ok)


def test_energy():
    assert abs(launch_energy_j(1.183, 13.0) - 0.5 * 1.183 * 169) < 1e-6


def test_force_and_accel_consistent():
    m, v, L = 1.183, 13.0, 1.3
    f = required_force_n(m, v, L)
    assert abs(exit_speed_ms(f, L, m) - v) < 1e-6          # оборотність
    assert 5 < launch_accel_g(v, L) < 9                     # ~6-7 g на 1.3 м


def test_pneumatic_pressure_is_low():
    # ~77 Н на ~40мм поршень -> низький тиск (< 2 бар)
    p = pneumatic_pressure_bar(77, 40)
    assert 0.3 < p < 2.0


def test_bungee_peaks_higher_than_pneumatic():
    avg = launch_accel_g(13.0, 1.3)
    assert bungee_peak_g(avg) > avg                         # бунджі б'є вищим піком


def test_deploy_margin():
    assert wing_deploy_margin_ok(13.0, 9.06) is True
    assert wing_deploy_margin_ok(10.0, 9.06) is False
