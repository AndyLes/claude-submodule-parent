"""Перевірка міцності планера E3 (раніше не робилася).

Ключові навантаження тубусного інтерсептора:
1. Прискорення старту (труба/бунджі) -> осьова сила на фюзеляж і утримання носа.
2. Згин лонжерона крила під перевантаженням (маневр/поривом) -> головний ризик.
3. Аеро-межа: яке перевантаження виникає при повному кермі на макс. швидкості.

Крило НЕ суцільне (це важило б ~600 г) — несуча = лонжерон (вуглепластиковий
пруток), друкована оболонка лише формоутворює. Тож рахуємо лонжерон."""
import math

G = 9.80665


def launch_accel_g(exit_speed_ms, tube_len_m):
    """Прискорення в трубі (рівноприскорено): a = v^2 / (2L). Повертає у g."""
    return exit_speed_ms ** 2 / (2 * tube_len_m) / G


def axial_launch_force_n(auw_kg, accel_g):
    """Осьова сила інерції на фюзеляж/утримання носа при старті."""
    return auw_kg * accel_g * G


def wing_root_moment_nm(auw_kg, load_factor, semi_span_m, centroid_frac=0.4):
    """Кореневий згинний момент однієї консолі крила при перевантаженні n.
    Підйомна ділиться навпіл; центр тиску консолі ~0.4 піврозмаху."""
    lift_panel_n = load_factor * auw_kg * G / 2.0
    return lift_panel_n * semi_span_m * centroid_frac


def tube_section_modulus_mm3(od_mm, id_mm=0.0):
    """Момент опору круглого перерізу (суцільний або трубка), мм^3."""
    I = math.pi * (od_mm ** 4 - id_mm ** 4) / 64.0
    return I / (od_mm / 2.0)


def spar_stress_mpa(moment_nm, od_mm, id_mm=0.0):
    """Згинне напруження в лонжероні (Н*м -> Н*мм / мм^3 = МПа)."""
    return (moment_nm * 1000.0) / tube_section_modulus_mm3(od_mm, id_mm)


def max_load_factor(auw_kg, semi_span_m, od_mm, id_mm, sigma_allow_mpa, centroid_frac=0.4):
    """Гранично допустиме перевантаження за міцністю лонжерона (лінійно по n)."""
    m1 = wing_root_moment_nm(auw_kg, 1.0, semi_span_m, centroid_frac)
    sigma1 = spar_stress_mpa(m1, od_mm, id_mm)
    return sigma_allow_mpa / sigma1


def aero_limit_load_factor(v_ms, s_m2, cl_max, auw_kg, rho=1.225):
    """Максимальне перевантаження, яке крило здатне створити на швидкості v
    (n = L_max / W). Вище цього кермо не підніме — межа обвідної."""
    l_max = 0.5 * rho * v_ms ** 2 * s_m2 * cl_max
    return l_max / (auw_kg * G)


def solid_plate_wing_mass_g(semi_span_mm, avg_chord_mm, thick_mm, rho_petg=1270.0, panels=2):
    """Маса суцільного крила-плити (щоб показати, чому воно МУСИТЬ бути порожнистим)."""
    vol_mm3 = semi_span_mm * avg_chord_mm * thick_mm * panels
    return vol_mm3 / 1000.0 * (rho_petg / 1000.0)
