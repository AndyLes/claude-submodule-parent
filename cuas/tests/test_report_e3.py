from cuas.design.report_e3 import build_report


def test_report_keys_and_gates():
    r = build_report()
    for k in ("auw_g", "cg_x_mm", "wing_loading_g_dm2", "stall_kmh", "launch_kmh",
              "top_speed_6s_kmh", "top_speed_4s_test_kmh", "flies_6s", "flies_4s_test",
              "ram_ke_6s_j", "glide_km_from_500m", "tail_volume_coeff", "tail_ok",
              "servo_req_kgcm", "servo_ok"):
        assert k in r
    assert r["flies_6s"] is True and r["flies_4s_test"] is True          # летить на обох
    assert r["top_speed_6s_kmh"] > r["top_speed_4s_test_kmh"] > r["stall_kmh"]  # 6S швидше за 4S
    assert r["tail_ok"] is True                                          # стійкість
    assert r["servo_ok"] is True                                        # MG90S тримає кермо на 6S


def test_bad_prop_does_not_fly_4s():
    bad = build_report(pitch_in=2.0, kv=1250)
    assert bad["flies_4s_test"] is False                                # 9x2 не літає
