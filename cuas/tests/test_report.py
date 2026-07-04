from cuas.design.report import build_report


def test_report_keys_and_acceptance():
    r = build_report()
    for k in ("auw_g", "com_mm", "twr", "vertical_accel_g", "top_speed_kmh",
              "drag_at_vmax_n", "power_at_vmax_w", "flight_time_min", "ram_ke_j",
              "arm_mode_hz", "hover_exc_hz", "resonance_ok"):
        assert k in r
    assert r["twr"] >= 5.0                       # acceptance: достатня тяга
    assert 120 <= r["top_speed_kmh"] <= 220      # acceptance: реалістична макс. швидкість
    assert r["resonance_ok"] is True             # acceptance: рама не резонує в польоті
    assert abs(r["com_mm"][0]) <= 15.0           # acceptance: CoM центрований (квадру потрібен баланс)
    assert abs(r["com_mm"][1]) <= 5.0            # acceptance: без лівого/правого дисбалансу
