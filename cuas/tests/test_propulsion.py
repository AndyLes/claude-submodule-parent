from cuas.design.propulsion import (thrust_total_g, twr, pitch_speed_ms, drag_force_n,
                                    top_speed_ms, vertical_accel_g, flight_time_min)


def test_twr():
    assert twr(thrust_total_g(1000), 800) == 5.0


def test_pitch_speed_scales_with_kv():
    assert pitch_speed_ms(2600, 25.2, 4.3) > pitch_speed_ms(1960, 25.2, 4.3) > 0


def test_top_speed_pitch_limited_is_realistic():
    # 6S 1960KV 5x4.3, big thrust -> pitch*level binds; realistic 5" top ~150-187 km/h
    v = top_speed_ms(1960, 25.2, 4.3, thrust_max_n=53.0, weight_n=7.8, cd=1.0, area_m2=0.012)
    assert 40 <= v <= 52          # m/s


def test_drag_grows_with_speed():
    assert drag_force_n(40, 1.0, 0.012) > drag_force_n(20, 1.0, 0.012)


def test_vertical_accel_g():
    assert vertical_accel_g(53.0, 7.8) == (53.0 - 7.8) / 7.8


def test_flight_time_positive():
    assert flight_time_min(1.3, 22.2, 0.85, 0.85, 400.0) > 0
