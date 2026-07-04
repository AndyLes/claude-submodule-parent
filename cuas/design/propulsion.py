"""Пропульсія та аеродинаміка E2. Свідомо: макс. швидкість квадра обмежена
кроком/розвантаженням пропа (а не пласким опором), тож top_speed = pitch*level.
Плаский опір лишаємо як верхню санітарну межу."""
import math

G = 9.80665


def thrust_total_g(thrust_per_motor_g, n=4):
    return thrust_per_motor_g * n


def twr(thrust_total_g, auw_g):
    return thrust_total_g / auw_g


def loaded_rpm(kv, v_batt, eta_rpm=0.65):
    return kv * v_batt * eta_rpm


def pitch_speed_ms(kv, v_batt, pitch_in, eta_rpm=0.65):
    """Теоретична швидкість за кроком пропа (без опору): RPM_loaded * pitch."""
    return loaded_rpm(kv, v_batt, eta_rpm) * (pitch_in * 0.0254) / 60.0


def drag_force_n(v_ms, cd, area_m2, rho=1.225):
    return 0.5 * rho * cd * area_m2 * v_ms ** 2


def drag_limited_speed_ms(thrust_max_n, weight_n, cd, area_m2, rho=1.225):
    """Санітарна межа: forward-складова тяги = плаский опір (forward=sqrt(T^2-W^2))."""
    if thrust_max_n <= weight_n:
        return 0.0
    forward = math.sqrt(thrust_max_n ** 2 - weight_n ** 2)
    return math.sqrt(2 * forward / (rho * cd * area_m2))


def top_speed_ms(kv, v_batt, pitch_in, thrust_max_n, weight_n, cd, area_m2,
                 level_factor=0.8, eta_rpm=0.65, rho=1.225):
    """Реальна макс. горизонтальна швидкість = min(pitch*level, пласка межа)."""
    return min(pitch_speed_ms(kv, v_batt, pitch_in, eta_rpm) * level_factor,
               drag_limited_speed_ms(thrust_max_n, weight_n, cd, area_m2, rho))


def vertical_accel_g(thrust_total_n, weight_n):
    """Пікове вертикальне прискорення у g = (T-W)/W. Міра «різкості»/скоропідйомності."""
    return (thrust_total_n - weight_n) / weight_n


def flight_time_min(cap_ah, v_nom, dod, eta, avg_power_w):
    energy_wh = cap_ah * v_nom * dod * eta
    return energy_wh / avg_power_w * 60.0
