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
