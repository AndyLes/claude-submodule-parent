"""ТТХ-звіт E3 (пушер-інтерсептор, складане монопланне крило) + CLI.
Проєкт під 6S (розрахунковий Vmax), тест на 4S. Порівняння тугості розвороту з хрестом."""
from cuas.design import e3_config as cfg
from cuas.design.mass import auw_g, center_of_mass_mm
from cuas.design.ram import kinetic_energy_j
from cuas.design.fixedwing import (wing_loading_g_dm2, stall_speed_ms, launch_speed_ms,
                                   pitch_speed_ms, flies, glide_range_km, tail_volume_coeff,
                                   dynamic_pressure_pa, hinge_moment_nm, servo_torque_required_kgcm,
                                   turn_radius_min_m, tube_id_required_mm)

# Довідка: попередня хрест-схема (для порівняння тугості розвороту)
_CRUCIFORM_AUW_KG = 1.249
_CRUCIFORM_S_M2 = 0.14
_CRUCIFORM_CL = 0.9


def build_report(pitch_in=None, kv=None):
    pitch_in = cfg.PROP_PITCH_IN if pitch_in is None else pitch_in
    kv = cfg.MOTOR_KV if kv is None else kv

    auw = auw_g(cfg.COMPONENTS)
    auw_kg = auw / 1000.0
    com = center_of_mass_mm([{**c, "y_mm": 0, "z_mm": 0} for c in cfg.COMPONENTS])
    s_m2 = cfg.WING_AREA_DM2 / 100.0

    stall = stall_speed_ms(auw_kg, s_m2, cfg.CL_MAX)
    launch = launch_speed_ms(stall, cfg.LAUNCH_MARGIN)
    top6s = pitch_speed_ms(kv, cfg.V_BATT_FULL, pitch_in, cfg.ETA_RPM)
    top4s = pitch_speed_ms(kv, cfg.V_BATT_TEST_FULL, pitch_in, cfg.ETA_RPM)
    ke = kinetic_energy_j(auw_kg, top6s)
    vt = tail_volume_coeff(cfg.TAIL_AREA_DM2, cfg.TAIL_ARM_MM, cfg.WING_AREA_DM2, cfg.WING_MAC_MM)

    r_turn = turn_radius_min_m(auw_kg, s_m2, cfg.CL_MAX)
    r_cruciform = turn_radius_min_m(_CRUCIFORM_AUW_KG, _CRUCIFORM_S_M2, _CRUCIFORM_CL)

    q = dynamic_pressure_pa(top6s)
    hm = hinge_moment_nm(cfg.CS_HINGE_COEFF, q, cfg.CS_AREA_DM2 / 100.0, cfg.CS_CHORD_MM / 1000.0)
    servo_req = servo_torque_required_kgcm(hm, cfg.SERVO_HORN_RATIO)
    tube_id = tube_id_required_mm(cfg.BODY_D_MM, cfg.TAIL_FIN_SPAN_MM, cfg.WING_FOLD_THICK_MM)

    return {
        "auw_g": round(auw, 1),
        "cg_x_mm": round(com[0], 1),
        "wing_loading_g_dm2": round(wing_loading_g_dm2(auw, cfg.WING_AREA_DM2), 1),
        "stall_kmh": round(stall * 3.6, 1),
        "launch_kmh": round(launch * 3.6, 1),
        "top_speed_6s_kmh": round(top6s * 3.6, 1),
        "top_speed_4s_test_kmh": round(top4s * 3.6, 1),
        "flies_6s": flies(top6s, stall),
        "flies_4s_test": flies(top4s, stall),
        "ram_ke_6s_j": round(ke, 0),
        "turn_radius_m": round(r_turn, 1),
        "turn_radius_cruciform_m": round(r_cruciform, 1),
        "turn_tighter_x": round(r_cruciform / r_turn, 2),   # у скільки разів тугіший розворот
        "glide_km_from_500m": round(glide_range_km(500, cfg.LD_GLIDE), 2),
        "tail_volume_coeff": round(vt, 2),
        "tail_ok": 0.35 <= vt <= 0.7,
        "servo_req_kgcm": round(servo_req, 2),
        "servo_ok": servo_req < cfg.SERVO_TORQUE_KGCM,
        "tube_id_required_mm": round(tube_id, 0),
    }


def _print(r, title):
    print(title)
    for k, v in r.items():
        print(f"{k:24}: {v}")


if __name__ == "__main__":
    _print(build_report(), '=== E3 folding-wing interceptor — TTX (design 6S, test 4S; 1200KV + 7x6) ===')
    print()
    bad = build_report(pitch_in=2.0, kv=1250)
    print('--- for comparison, 9x2 prop + X2212-1250 on 4S ---')
    print(f"  top_speed_4s_test_kmh: {bad['top_speed_4s_test_kmh']}  stall: {bad['stall_kmh']}  FLIES(4S): {bad['flies_4s_test']}")
