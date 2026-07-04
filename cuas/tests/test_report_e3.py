from cuas.design.report_e3 import build_report


def test_report_keys_and_gates():
    r = build_report()
    for k in ("auw_g", "cg_x_mm", "wing_loading_g_dm2", "stall_kmh", "launch_kmh",
              "top_speed_6s_kmh", "top_speed_4s_test_kmh", "flies_6s", "flies_4s_test",
              "ram_ke_6s_j", "turn_radius_m", "turn_radius_cruciform_m", "turn_tighter_x",
              "glide_km_from_500m", "tail_volume_coeff", "tail_ok", "servo_req_kgcm",
              "servo_ok", "tube_id_required_mm"):
        assert k in r
    assert r["flies_6s"] is True and r["flies_4s_test"] is True
    assert r["top_speed_6s_kmh"] > r["top_speed_4s_test_kmh"] > r["stall_kmh"]
    assert r["tail_ok"] is True
    assert r["servo_ok"] is True


def test_monoplane_turns_tighter_than_cruciform():
    r = build_report()
    assert r["turn_radius_m"] < r["turn_radius_cruciform_m"]   # моноплан тугіший
    assert r["turn_tighter_x"] > 1.4                           # відчутно (>1.4x)


def test_bad_prop_too_slow_to_intercept():
    # з більшим крилом 9x2 технічно злітає (~46 км/год), але це нижче за швидкість
    # будь-якої цілі (Орлан 110+) -> перехопити неможливо.
    bad = build_report(pitch_in=2.0, kv=1250)
    assert bad["top_speed_4s_test_kmh"] < 60
