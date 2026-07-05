import math
from cuas.design import e3_config as cfg
from cuas.design.thermal import (motor_heat_w, resistive_heat_w, soak_temp_rise_c,
                                 safe_soak_minutes, blended_c_jkgk, required_airflow_m3s,
                                 inlet_mass_flow_kgs, coolant_dt_c, inlet_area_needed_cm2,
                                 battery_temp_rise_c)


def test_motor_heat():
    assert abs(motor_heat_w(1000, 0.85) - 150.0) < 1e-6


def test_resistive_heat():
    assert abs(resistive_heat_w(45, 0.03) - 45 * 45 * 0.03) < 1e-6


def test_soak_rise_and_safe_minutes_invert():
    # ΔT after safe_minutes must equal the allowed ΔT (round-trip)
    P, m, c, dT = 8.4, 45.0, 750.0, 45.0
    t = safe_soak_minutes(P, m, c, dT)
    assert abs(soak_temp_rise_c(P, m, c, t) - dT) < 1e-6


def test_soak_no_heat_is_infinite():
    assert safe_soak_minutes(0.0, 45, 750, 45) == math.inf


def test_all_on_soak_is_the_short_one():
    # VTX + full Pi in a sealed tube: only a few minutes on bare boards
    heat_all = cfg.HEAT_PI_W + cfg.HEAT_VTX_W + cfg.HEAT_FC_W + cfg.HEAT_CAM_W + cfg.HEAT_RX_W
    bare = safe_soak_minutes(heat_all, cfg.SOAK_LOCAL_MASS_G, cfg.SOAK_LOCAL_C_JKGK, cfg.SOAK_DT_ALLOW_C)
    assert 2.0 < bare < 4.5                                       # ~3 min — the real limit


def test_gating_and_spreader_multiply_dwell():
    heat_all = cfg.HEAT_PI_W + cfg.HEAT_VTX_W + cfg.HEAT_FC_W + cfg.HEAT_CAM_W + cfg.HEAT_RX_W
    heat_gated = cfg.HEAT_PI_IDLE_W + cfg.HEAT_FC_W + cfg.HEAT_CAM_W + cfg.HEAT_RX_W  # VTX off, Pi idle
    m = cfg.SOAK_LOCAL_MASS_G + cfg.SPREADER_MASS_G
    c = blended_c_jkgk([cfg.SOAK_LOCAL_MASS_G, cfg.SPREADER_MASS_G],
                       [cfg.SOAK_LOCAL_C_JKGK, cfg.SPREADER_C_JKGK])
    bare = safe_soak_minutes(heat_all, cfg.SOAK_LOCAL_MASS_G, cfg.SOAK_LOCAL_C_JKGK, cfg.SOAK_DT_ALLOW_C)
    fixed = safe_soak_minutes(heat_gated, m, c, cfg.SOAK_DT_ALLOW_C)
    assert fixed > 4 * bare                                       # gate+spreader → >4× dwell
    assert fixed > 15.0                                           # operationally usable (>15 min)


def test_flight_bay_cooling_ok_at_launch_speed():
    # bay heat in flight (ESC + all avionics); motor is external-cooled
    bay_heat = (resistive_heat_w(cfg.ESC_CURRENT_SPRINT_A, cfg.ESC_R_OHM)
                + cfg.HEAT_PI_W + cfg.HEAT_VTX_W + cfg.HEAT_FC_W + cfg.HEAT_CAM_W + cfg.HEAT_RX_W)
    area = cfg.INLET_COUNT * cfg.INLET_W_MM * cfg.INLET_DEPTH_MM / 100.0  # cm²
    v_launch = 27.8
    mdot = inlet_mass_flow_kgs(area, v_launch, cfg.AIR_RHO, cfg.NACA_INLET_EFF)
    q = mdot / cfg.AIR_RHO
    dt = coolant_dt_c(bay_heat, q, cfg.AIR_RHO, cfg.AIR_CP)
    assert dt < cfg.COOL_DT_AIR_C                                 # even at slow launch speed, air ΔT under limit
    # provided area exceeds the area needed for the same heat
    need = inlet_area_needed_cm2(bay_heat, cfg.COOL_DT_AIR_C, v_launch, cfg.AIR_RHO, cfg.AIR_CP, cfg.NACA_INLET_EFF)
    assert area > need


def test_battery_stays_cool_for_short_mission():
    dT = battery_temp_rise_c(cfg.BATT_CURRENT_SPRINT_A, cfg.BATT_R_OHM, cfg.MISSION_SPRINT_S,
                             cfg.BATT_MASS_G, cfg.BATT_C_JKGK)
    assert dT < 10.0                                             # short sprint → no active cooling needed
    assert cfg.T_AMBIENT_C + dT < cfg.T_BATT_MAX_C
