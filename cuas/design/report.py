"""ТТХ-звіт E2 з єдиного конфіга + CLI."""
from cuas.design import e2_config as cfg
from cuas.design.mass import auw_g, center_of_mass_mm
from cuas.design.propulsion import (thrust_total_g, twr, top_speed_ms, drag_force_n,
                                     vertical_accel_g, flight_time_min, loaded_rpm, G)
from cuas.design.ram import kinetic_energy_j, arm_first_mode_hz, hover_rotation_hz


def build_report():
    auw = auw_g(cfg.COMPONENTS)
    com = center_of_mass_mm(cfg.COMPONENTS)
    thrust_g = thrust_total_g(cfg.THRUST_PER_MOTOR_G)
    thrust_n = thrust_g / 1000.0 * G
    weight_n = auw / 1000.0 * G

    vmax = top_speed_ms(cfg.MOTOR_KV, cfg.V_BATT_FULL, cfg.PROP_PITCH_IN, thrust_n, weight_n,
                        cfg.CD_BODY, cfg.FRONTAL_AREA_M2, cfg.LEVEL_FACTOR, cfg.ETA_RPM)
    drag_v = drag_force_n(vmax, cfg.CD_BODY, cfg.FRONTAL_AREA_M2)
    ft = flight_time_min(cfg.BATT_CAP_AH, cfg.V_BATT_NOMINAL, cfg.BATT_DOD, cfg.BATT_ETA, cfg.EST_AVG_POWER_W)
    ke = kinetic_energy_j(auw / 1000.0, vmax)

    rpm_max = loaded_rpm(cfg.MOTOR_KV, cfg.V_BATT_FULL, cfg.ETA_RPM)
    t_max_motor_n = cfg.THRUST_PER_MOTOR_G / 1000.0 * G
    t_hover_motor_n = weight_n / 4.0
    arm_hz = arm_first_mode_hz(cfg.ARM_W_MM, cfg.ARM_H_MM, cfg.ARM_LEN_MM, cfg.MOTOR_MASS_G,
                               cfg.E_PETG_PA, cfg.RHO_PETG)
    hover_hz = hover_rotation_hz(rpm_max, t_max_motor_n, t_hover_motor_n)

    return {
        "auw_g": round(auw, 1),
        "com_mm": tuple(round(v, 1) for v in com),
        "twr": round(twr(thrust_g, auw), 2),
        "vertical_accel_g": round(vertical_accel_g(thrust_n, weight_n), 2),
        "top_speed_kmh": round(vmax * 3.6, 1),
        "drag_at_vmax_n": round(drag_v, 1),
        "power_at_vmax_w": round(drag_v * vmax, 0),
        "flight_time_min": round(ft, 1),
        "ram_ke_j": round(ke, 0),
        "arm_mode_hz": round(arm_hz, 1),
        "hover_exc_hz": round(hover_hz, 1),
        "resonance_ok": arm_hz < hover_hz,   # власна частота нижче збудження на висінні
    }


def _print(r):
    print('=== E2 5" auto-ram — TTX ===')
    for k, v in r.items():
        print(f"{k:18}: {v}")


if __name__ == "__main__":
    _print(build_report())
