"""ТТХ-звіт E3 (хрестокрилий пушер-інтерсептор) + CLI.
Проєкт під 6S (розрахунковий Vmax), тест на 4S (м'якший режим)."""
from cuas.design import e3_config as cfg
from cuas.design.mass import auw_g, center_of_mass_mm
from cuas.design.ram import kinetic_energy_j
from cuas.design.fixedwing import (wing_loading_g_dm2, stall_speed_ms, launch_speed_ms,
                                   pitch_speed_ms, flies, glide_range_km, tail_volume_coeff,
                                   dynamic_pressure_pa, hinge_moment_nm, servo_torque_required_kgcm)


def build_report(pitch_in=None, kv=None):
    pitch_in = cfg.PROP_PITCH_IN if pitch_in is None else pitch_in
    kv = cfg.MOTOR_KV if kv is None else kv

    auw = auw_g(cfg.COMPONENTS)
    auw_kg = auw / 1000.0
    com = center_of_mass_mm([{**c, "y_mm": 0, "z_mm": 0} for c in cfg.COMPONENTS])
    s_m2 = cfg.WING_AREA_DM2 / 100.0

    stall = stall_speed_ms(auw_kg, s_m2, cfg.CL_MAX)
    launch = launch_speed_ms(stall, cfg.LAUNCH_MARGIN)
    top6s = pitch_speed_ms(kv, cfg.V_BATT_FULL, pitch_in, cfg.ETA_RPM)         # 6S design
    top4s = pitch_speed_ms(kv, cfg.V_BATT_TEST_FULL, pitch_in, cfg.ETA_RPM)    # 4S test
    ke = kinetic_energy_j(auw_kg, top6s)
    vt = tail_volume_coeff(cfg.TAIL_AREA_DM2, cfg.TAIL_ARM_MM, cfg.WING_AREA_DM2, cfg.WING_MAC_MM)

    # Кермо: шарнірний момент на розрахунковій (6S) швидкості vs момент MG90S
    q = dynamic_pressure_pa(top6s)
    hm = hinge_moment_nm(cfg.CS_HINGE_COEFF, q, cfg.CS_AREA_DM2 / 100.0, cfg.CS_CHORD_MM / 1000.0)
    servo_req = servo_torque_required_kgcm(hm, cfg.SERVO_HORN_RATIO)

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
        "glide_km_from_500m": round(glide_range_km(500, cfg.LD_GLIDE), 2),
        "tail_volume_coeff": round(vt, 2),
        "tail_ok": 0.35 <= vt <= 0.7,
        "servo_req_kgcm": round(servo_req, 2),
        "servo_ok": servo_req < cfg.SERVO_TORQUE_KGCM,   # MG90S тримає кермо на 6S-швидкості
    }


def _print(r, title):
    print(title)
    for k, v in r.items():
        print(f"{k:22}: {v}")


if __name__ == "__main__":
    _print(build_report(), '=== E3 X-wing missile — TTX (design 6S, test 4S; 1200KV + 7x6) ===')
    print()
    bad = build_report(pitch_in=2.0, kv=1250)
    print('--- for comparison, 9x2 prop + X2212-1250 on 4S ---')
    print(f"  top_speed_4s_test_kmh: {bad['top_speed_4s_test_kmh']}  stall: {bad['stall_kmh']}  FLIES(4S): {bad['flies_4s_test']}")
