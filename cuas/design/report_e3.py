"""ТТХ-звіт E3 (хрестокрилий пушер-інтерсептор) + CLI."""
from cuas.design import e3_config as cfg
from cuas.design.mass import auw_g, center_of_mass_mm
from cuas.design.ram import kinetic_energy_j
from cuas.design.fixedwing import (wing_loading_g_dm2, stall_speed_ms, launch_speed_ms,
                                   pitch_speed_ms, flies, glide_range_km, tail_volume_coeff)


def build_report(pitch_in=None, kv=None):
    pitch_in = cfg.PROP_PITCH_IN if pitch_in is None else pitch_in
    kv = cfg.MOTOR_KV if kv is None else kv

    auw = auw_g(cfg.COMPONENTS)
    auw_kg = auw / 1000.0
    com = center_of_mass_mm([{**c, "y_mm": 0, "z_mm": 0} for c in cfg.COMPONENTS])
    s_m2 = cfg.WING_AREA_DM2 / 100.0

    stall = stall_speed_ms(auw_kg, s_m2, cfg.CL_MAX)
    launch = launch_speed_ms(stall, cfg.LAUNCH_MARGIN)
    top = pitch_speed_ms(kv, cfg.V_BATT_FULL, pitch_in, cfg.ETA_RPM)
    ke = kinetic_energy_j(auw_kg, top)
    vt = tail_volume_coeff(cfg.TAIL_AREA_DM2, cfg.TAIL_ARM_MM, cfg.WING_AREA_DM2, cfg.WING_MAC_MM)

    return {
        "auw_g": round(auw, 1),
        "cg_x_mm": round(com[0], 1),
        "wing_loading_g_dm2": round(wing_loading_g_dm2(auw, cfg.WING_AREA_DM2), 1),
        "stall_kmh": round(stall * 3.6, 1),
        "launch_kmh": round(launch * 3.6, 1),
        "top_speed_kmh": round(top * 3.6, 1),
        "flies": flies(top, stall),
        "ram_ke_j": round(ke, 0),
        "glide_km_from_500m": round(glide_range_km(500, cfg.LD_GLIDE), 2),
        "tail_volume_coeff": round(vt, 2),
        "tail_ok": 0.35 <= vt <= 0.7,
    }


def _print(r, title):
    print(title)
    for k, v in r.items():
        print(f"{k:20}: {v}")


if __name__ == "__main__":
    _print(build_report(), '=== E3 X-wing missile — TTX (recommended: 1600KV + 7x6) ===')
    print()
    bad = build_report(pitch_in=2.0, kv=1250)
    print('--- for comparison, your 9x2 prop + X2212-1250 ---')
    print(f"  top_speed_kmh: {bad['top_speed_kmh']}  stall_kmh: {bad['stall_kmh']}  FLIES: {bad['flies']}")
