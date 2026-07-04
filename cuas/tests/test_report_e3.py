from cuas.design.report_e3 import build_report


def test_report_flies_and_keys():
    r = build_report()
    for k in ("auw_g", "cg_x_mm", "wing_loading_g_dm2", "stall_kmh", "launch_kmh",
              "top_speed_kmh", "flies", "ram_ke_j", "glide_km_from_500m",
              "tail_volume_coeff", "tail_ok"):
        assert k in r
    assert r["flies"] is True                                      # рекомендований проп літає
    assert r["top_speed_kmh"] > r["launch_kmh"] > r["stall_kmh"]   # порядок швидкостей адекватний
    assert r["tail_ok"] is True                                    # стійкість у нормі


def test_bad_prop_does_not_fly():
    bad = build_report(pitch_in=2.0, kv=1250)
    assert bad["flies"] is False                                   # 9x2 не літає
