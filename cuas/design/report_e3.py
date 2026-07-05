"""ТТХ-звіт E3 (компактний тубусний пушер-інтерсептор) + CLI.
Площа/MAC крила ОБЧИСЛЮЮТЬСЯ з геометрії (CAD ↔ розрахунок узгоджені). Проєкт 6S, тест 4S."""
from cuas.design import e3_config as cfg
from cuas.design.mass import auw_g, center_of_mass_mm
from cuas.design.ram import kinetic_energy_j
from cuas.design.fixedwing import (wing_area_dm2, wing_mac_mm, wing_loading_g_dm2, stall_speed_ms,
                                   launch_speed_ms, pitch_speed_ms, flies, glide_range_km,
                                   tail_volume_coeff, dynamic_pressure_pa, hinge_moment_nm,
                                   servo_torque_required_kgcm, turn_radius_min_m, tube_id_required_mm)
from cuas.design.thermal import (motor_heat_w, resistive_heat_w, safe_soak_minutes, blended_c_jkgk,
                                 inlet_mass_flow_kgs, coolant_dt_c, battery_temp_rise_c)


def build_report(pitch_in=None, kv=None):
    pitch_in = cfg.PROP_PITCH_IN if pitch_in is None else pitch_in
    kv = cfg.MOTOR_KV if kv is None else kv

    auw = auw_g(cfg.COMPONENTS)
    auw_kg = auw / 1000.0
    com = center_of_mass_mm([{**c, "y_mm": 0, "z_mm": 0} for c in cfg.COMPONENTS])

    area_dm2 = wing_area_dm2(cfg.WING_SEMISPAN_MM, cfg.WING_ROOT_C_MM, cfg.WING_TIP_C_MM)  # з геометрії
    mac = wing_mac_mm(cfg.WING_ROOT_C_MM, cfg.WING_TIP_C_MM)
    s_m2 = area_dm2 / 100.0

    stall = stall_speed_ms(auw_kg, s_m2, cfg.CL_MAX)
    launch = launch_speed_ms(stall, cfg.LAUNCH_MARGIN)
    top6s = pitch_speed_ms(kv, cfg.V_BATT_FULL, pitch_in, cfg.ETA_RPM)
    top4s = pitch_speed_ms(kv, cfg.V_BATT_TEST_FULL, pitch_in, cfg.ETA_RPM)
    ke = kinetic_energy_j(auw_kg, top6s)
    vt = tail_volume_coeff(cfg.TAIL_AREA_DM2, cfg.TAIL_ARM_MM, area_dm2, mac)
    r_turn = turn_radius_min_m(auw_kg, s_m2, cfg.CL_MAX)

    q = dynamic_pressure_pa(top6s)
    hm = hinge_moment_nm(cfg.CS_HINGE_COEFF, q, cfg.CS_AREA_DM2 / 100.0, cfg.CS_CHORD_MM / 1000.0)
    servo_req = servo_torque_required_kgcm(hm, cfg.SERVO_HORN_RATIO)
    tube_id = tube_id_required_mm(cfg.BODY_D_MM, cfg.TAIL_FIN_SPAN_MM, cfg.WING_FOLD_THICK_MM)

    return {
        "auw_g": round(auw, 1),
        "cg_x_mm": round(com[0], 1),
        "wing_area_dm2": round(area_dm2, 2),                 # з геометрії CAD
        "wing_loading_g_dm2": round(wing_loading_g_dm2(auw, area_dm2), 1),
        "stall_kmh": round(stall * 3.6, 1),
        "launch_kmh": round(launch * 3.6, 1),
        "top_speed_6s_kmh": round(top6s * 3.6, 1),
        "top_speed_4s_test_kmh": round(top4s * 3.6, 1),
        "flies_6s": flies(top6s, stall),
        "flies_4s_test": flies(top4s, stall),
        "ram_ke_6s_j": round(ke, 0),
        "turn_radius_m": round(r_turn, 1),                  # широкий (компакт) -> ставка на pixel-lock
        "glide_km_from_500m": round(glide_range_km(500, cfg.LD_GLIDE), 2),
        "tail_volume_coeff": round(vt, 2),
        "tail_ok": 0.35 <= vt <= 0.7,
        "servo_req_kgcm": round(servo_req, 2),
        "servo_ok": servo_req < cfg.SERVO_TORQUE_KGCM,
        "tube_id_required_mm": round(tube_id, 0),
    }


def build_thermal(v_launch_ms=27.8):
    """Термо-зведення: соук у трубі (реальний ліміт) + обдув у польоті + батарея."""
    heat_all = cfg.HEAT_PI_W + cfg.HEAT_VTX_W + cfg.HEAT_FC_W + cfg.HEAT_CAM_W + cfg.HEAT_RX_W
    heat_gated = cfg.HEAT_PI_IDLE_W + cfg.HEAT_FC_W + cfg.HEAT_CAM_W + cfg.HEAT_RX_W  # VTX off, Pi idle
    m_fix = cfg.SOAK_LOCAL_MASS_G + cfg.SPREADER_MASS_G
    c_fix = blended_c_jkgk([cfg.SOAK_LOCAL_MASS_G, cfg.SPREADER_MASS_G],
                           [cfg.SOAK_LOCAL_C_JKGK, cfg.SPREADER_C_JKGK])

    soak_bare = safe_soak_minutes(heat_all, cfg.SOAK_LOCAL_MASS_G, cfg.SOAK_LOCAL_C_JKGK, cfg.SOAK_DT_ALLOW_C)
    soak_fixed = safe_soak_minutes(heat_gated, m_fix, c_fix, cfg.SOAK_DT_ALLOW_C)

    esc_heat = resistive_heat_w(cfg.ESC_CURRENT_SPRINT_A, cfg.ESC_R_OHM)
    bay_heat = esc_heat + heat_all
    area_cm2 = cfg.INLET_COUNT * cfg.INLET_W_MM * cfg.INLET_DEPTH_MM / 100.0
    mdot = inlet_mass_flow_kgs(area_cm2, v_launch_ms, cfg.AIR_RHO, cfg.NACA_INLET_EFF)
    dt_air = coolant_dt_c(bay_heat, mdot / cfg.AIR_RHO, cfg.AIR_RHO, cfg.AIR_CP)

    batt_dT = battery_temp_rise_c(cfg.BATT_CURRENT_SPRINT_A, cfg.BATT_R_OHM, cfg.MISSION_SPRINT_S,
                                  cfg.BATT_MASS_G, cfg.BATT_C_JKGK)
    return {
        "motor_heat_w": round(motor_heat_w(cfg.MOTOR_POWER_IN_SPRINT_W, cfg.MOTOR_EFF), 0),  # обдув ЗЗОВНІ (пуш-проп)
        "esc_heat_w": round(esc_heat, 1),
        "bay_heat_flight_w": round(bay_heat, 1),
        "soak_min_all_on_bare": round(soak_bare, 1),          # усе ON, без розподільника — РЕАЛЬНИЙ ліміт
        "soak_min_gated_spreader": round(soak_fixed, 1),      # VTX off + Pi idle + алю-розподільник
        "soak_dwell_ok": soak_fixed >= 15.0,
        "cool_air_dt_at_launch_c": round(dt_air, 1),
        "inlet_area_cm2": round(area_cm2, 2),
        "flight_cooling_ok": dt_air < cfg.COOL_DT_AIR_C,
        "batt_rise_sprint_c": round(batt_dT, 1),
        "batt_peak_c": round(cfg.T_AMBIENT_C + batt_dT, 1),
        "batt_ok_passive": (cfg.T_AMBIENT_C + batt_dT) < cfg.T_BATT_MAX_C,   # короткий політ → без активного
    }


def _print(r, title):
    print(title)
    for k, v in r.items():
        print(f"{k:24}: {v}")


if __name__ == "__main__":
    _print(build_report(), '=== E3 folding-wing interceptor — TTX (design 6S, test 4S; 1200KV + 7x6) ===')
    print()
    _print(build_thermal(), '=== THERMAL — soak (tube) / flight airflow / battery ===')
    print()
    bad = build_report(pitch_in=2.0, kv=1250)
    print('--- for comparison, 9x2 prop + X2212-1250 on 4S ---')
    print(f"  top_speed_4s_test_kmh: {bad['top_speed_4s_test_kmh']}  stall: {bad['stall_kmh']}  FLIES(4S): {bad['flies_4s_test']}")
