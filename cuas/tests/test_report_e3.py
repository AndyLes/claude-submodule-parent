from cuas.design.report_e3 import build_report
from cuas.design.fixedwing import wing_area_dm2
from cuas.design import e3_config as cfg


def test_report_keys_and_gates():
    r = build_report()
    for k in ("auw_g", "cg_x_mm", "wing_area_dm2", "wing_loading_g_dm2", "stall_kmh", "launch_kmh",
              "top_speed_6s_kmh", "top_speed_4s_test_kmh", "flies_6s", "flies_4s_test",
              "ram_ke_6s_j", "turn_radius_m", "glide_km_from_500m", "tail_volume_coeff",
              "tail_ok", "servo_req_kgcm", "servo_ok", "tube_id_required_mm"):
        assert k in r
    assert r["flies_6s"] is True and r["flies_4s_test"] is True
    assert r["top_speed_6s_kmh"] > r["top_speed_4s_test_kmh"] > r["stall_kmh"]
    assert r["tail_ok"] is True
    assert r["servo_ok"] is True


def test_wing_area_matches_geometry():
    # запобіжник від минулої помилки (22 vs 4.8): площа у звіті = площа з геометрії CAD
    r = build_report()
    geo = wing_area_dm2(cfg.WING_SEMISPAN_MM, cfg.WING_ROOT_C_MM, cfg.WING_TIP_C_MM)
    assert abs(r["wing_area_dm2"] - round(geo, 2)) < 0.01


def test_compact_is_high_loading_wide_turn():
    # чесно: компакт -> високе навантаження, широкий розворот (ставка на pixel-lock)
    r = build_report()
    assert r["wing_loading_g_dm2"] > 150
    assert r["turn_radius_m"] > 20


def test_bad_prop_too_slow_to_intercept():
    bad = build_report(pitch_in=2.0, kv=1250)
    assert bad["top_speed_4s_test_kmh"] < 60
