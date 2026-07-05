"""Термо-модель E3 (компактний тубусний пушер-інтерсептор).

Головна нетривіальність: у польоті все просто — ПУШЕР-ПРОП працює витяжкою, тягне
повітря крізь фюзеляж (втоплені NACA-входи → бей → аутлет у зону розрідження за
корпусом), а сам мотор обдувається пропом. Реальний ризик — ПРЕ-СТАРТ: планер сидить
у ЗАКРИТІЙ трубі, мотор/ESC вимкнені (нуль обдуву), а авіоніка гріється. Аналоговий
VTX — найгарячіший дрібний вузол; за хвилини соуку в глухій трубі він перегрівається.

Тому термо-рахунок робимо у двох режимах:
1. СОУК (адіабатичний, зосереджена ємність) — скільки хвилин планер може «армованим»
   стояти в трубі до ліміту VTX. Ключові важелі: гейтити VTX + тримати Pi в ідлі до
   команди пуску; алюмінієвий тепло-розподільник додає теплову масу.
2. ПОЛІТ (стаціонарний обдув) — площа NACA-входів, щоб винести тепло бею; батарея —
   приріст за спринт (I^2R).
"""
import math


# ---------- тепловиділення джерел ----------
def motor_heat_w(power_in_w, eff):
    """Тепло мотора = вхідна потужність × (1 − ККД)."""
    return power_in_w * (1.0 - eff)


def resistive_heat_w(current_a, r_ohm):
    """Джоулеве тепло I^2·R (ESC або пакет батареї)."""
    return current_a * current_a * r_ohm


# ---------- соук у трубі (адіабатика, зосереджена ємність) ----------
def soak_temp_rise_c(heat_w, mass_g, c_jkgk, minutes):
    """Приріст температури вузла без обдуву: ΔT = P·t / (m·c)."""
    return heat_w * (minutes * 60.0) / (mass_g / 1000.0 * c_jkgk)


def safe_soak_minutes(heat_w, mass_g, c_jkgk, dt_allow_c):
    """Скільки хвилин до дозволеного приросту dt_allow (0 якщо тепла немає → інф)."""
    if heat_w <= 0:
        return math.inf
    return dt_allow_c * (mass_g / 1000.0 * c_jkgk) / (heat_w * 60.0)


def blended_c_jkgk(masses_g, cs_jkgk):
    """Ефективна теплоємність зібраного вузла (масо-зважена)."""
    m = sum(masses_g)
    return sum(mi * ci for mi, ci in zip(masses_g, cs_jkgk)) / m if m else 0.0


# ---------- обдув у польоті (стаціонар) ----------
def required_airflow_m3s(heat_w, dt_air_c, rho, cp):
    """Об'ємна витрата повітря, щоб винести heat_w при нагріві повітря на dt_air."""
    return heat_w / (rho * cp * dt_air_c)


def inlet_mass_flow_kgs(area_cm2, v_ms, rho, capture_eff):
    """Масова витрата крізь вхід площею area при швидкості v (з коеф. захоплення)."""
    return area_cm2 / 1e4 * v_ms * rho * capture_eff


def coolant_dt_c(heat_w, airflow_m3s, rho, cp):
    """Фактичний нагрів охолодного повітря при заданій витраті (зворотна перевірка)."""
    if airflow_m3s <= 0:
        return math.inf
    return heat_w / (rho * cp * airflow_m3s)


def inlet_area_needed_cm2(heat_w, dt_air_c, v_ms, rho, cp, capture_eff):
    """Потрібна площа входу під heat_w при швидкості v (см²)."""
    q = required_airflow_m3s(heat_w, dt_air_c, rho, cp)
    return q / (v_ms * capture_eff) * 1e4


# ---------- батарея ----------
def battery_temp_rise_c(current_a, r_ohm, seconds, mass_g, c_jkgk):
    """Приріст T батареї за спринт: I^2R·t / (m·c) (адіабатика — короткий політ)."""
    return resistive_heat_w(current_a, r_ohm) * seconds / (mass_g / 1000.0 * c_jkgk)
