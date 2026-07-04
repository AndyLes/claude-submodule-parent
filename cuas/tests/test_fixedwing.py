from cuas.design.fixedwing import (wing_loading_g_dm2, stall_speed_ms, launch_speed_ms,
                                   pitch_speed_ms, flies, glide_range_km, tail_volume_coeff,
                                   dynamic_pressure_pa, hinge_moment_nm, servo_torque_required_kgcm)


def test_wing_loading():
    assert wing_loading_g_dm2(1400, 14) == 100.0


def test_stall_grows_with_mass():
    assert stall_speed_ms(1.4, 0.14, 0.9) > stall_speed_ms(1.0, 0.14, 0.9)


def test_launch_above_stall():
    assert launch_speed_ms(12.0) == 15.0


def test_pitch_speed_scales_with_pitch():
    assert pitch_speed_ms(1600, 16.8, 6) > pitch_speed_ms(1600, 16.8, 2)


def test_low_pitch_prop_cannot_fly():
    # 9x2 (крок 2") на 4S -> стеля нижче зриву -> не літає
    top = pitch_speed_ms(1250, 16.8, 2)
    stall = stall_speed_ms(1.24, 0.14, 0.9)
    assert flies(top, stall) is False


def test_high_pitch_prop_flies():
    top = pitch_speed_ms(1600, 16.8, 6)
    stall = stall_speed_ms(1.24, 0.14, 0.9)
    assert flies(top, stall) is True


def test_glide_range():
    assert glide_range_km(500, 8) == 4.0


def test_tail_volume_positive():
    assert tail_volume_coeff(4.5, 280, 14, 140) > 0


def test_servo_torque_within_mg90s_at_200kmh():
    # ~200 км/год (55 м/с): MG90S (1.8 кг*см) має тримати малу кермову поверхню
    q = dynamic_pressure_pa(55.0)
    hm = hinge_moment_nm(0.22, q, 0.0035, 0.03)
    torque = servo_torque_required_kgcm(hm)
    assert q > 0 and hm > 0 and 0 < torque < 1.8


def test_higher_speed_needs_more_servo_torque():
    hm_fast = hinge_moment_nm(0.22, dynamic_pressure_pa(55.0), 0.0035, 0.03)
    hm_slow = hinge_moment_nm(0.22, dynamic_pressure_pa(37.0), 0.0035, 0.03)
    assert servo_torque_required_kgcm(hm_fast) > servo_torque_required_kgcm(hm_slow)
