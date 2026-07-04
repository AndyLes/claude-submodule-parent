"""Аеродинаміка/динаміка fixed-wing (ракетна форма): навантаження на крило,
зрив, швидкість сходу з труби, стеля швидкості за кроком пропа, планування,
хвостовий обсяг (стійкість), перевірка «чи взагалі полетить»."""
import math

G = 9.80665


def wing_loading_g_dm2(auw_g, s_dm2):
    return auw_g / s_dm2


def stall_speed_ms(auw_kg, s_m2, cl_max, rho=1.225):
    return math.sqrt(2 * auw_kg * G / (rho * s_m2 * cl_max))


def launch_speed_ms(stall_ms, margin=1.25):
    """Швидкість сходу з труби/катапульти — над зривом із запасом."""
    return stall_ms * margin


def pitch_speed_ms(kv, v_batt, pitch_in, eta_rpm=0.72):
    """Стеля швидкості за кроком пропа: RPM_loaded * pitch. Головний обмежувач Vmax літака."""
    rpm = kv * v_batt * eta_rpm
    return rpm * (pitch_in * 0.0254) / 60.0


def flies(top_ms, stall_ms, margin=1.15):
    """Чи здатний тягою вийти за зрив (інакше — падає)."""
    return top_ms >= stall_ms * margin


def glide_range_km(altitude_m, ld):
    """Дальність планування при відмові мотора."""
    return altitude_m * ld / 1000.0


def tail_volume_coeff(s_tail_dm2, arm_mm, s_wing_dm2, mac_mm):
    """Коефіцієнт хвостового обсягу V_t = (S_tail*l)/(S_wing*MAC). Норма ~0.35-0.6."""
    return (s_tail_dm2 * arm_mm) / (s_wing_dm2 * mac_mm)


def dynamic_pressure_pa(v_ms, rho=1.225):
    return 0.5 * rho * v_ms ** 2


def hinge_moment_nm(ch, q_pa, cs_area_m2, cs_chord_m):
    """Шарнірний момент кермової поверхні H = Ch * q * S_cs * c_cs (Н*м)."""
    return ch * q_pa * cs_area_m2 * cs_chord_m


def servo_torque_required_kgcm(hinge_moment_nm, horn_ratio=1.0):
    """Потрібний момент сервоприводу, кг*см (1 Н*м = 10.197 кг*см)."""
    return hinge_moment_nm * horn_ratio * 10.197


def turn_radius_min_m(auw_kg, s_m2, cl_max, rho=1.225):
    """Мінімальний радіус усталеного розвороту R = 2m/(rho*S*CL_max) [м].
    Менший = тугіший розворот = ефективніше перехоплення маневрованої цілі."""
    return 2 * auw_kg / (rho * s_m2 * cl_max)


def tube_id_required_mm(body_d_mm, tail_fin_span_mm, wing_fold_thick_mm):
    """Потрібний внутрішній діаметр пускової труби: фюзеляж + найбільший
    нескладений виступ (фіксовані фіни або складене крило) з обох боків."""
    return body_d_mm + 2 * max(tail_fin_span_mm, wing_fold_thick_mm)
