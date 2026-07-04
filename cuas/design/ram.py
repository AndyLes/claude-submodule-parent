"""Енергія тарана + структурна динаміка друкованого променя.

Головний ризик друкованої рами — НЕ аеро-згин (аеро-навантаження на промінь мале),
а РЕЗОНАНС: перша власна частота променя не має потрапляти в робочий діапазон
збудження від ротора. Тож рахуємо власну частоту (консоль із масою мотора на кінці)
і порівнюємо з частотою обертання на висінні."""
import math


def kinetic_energy_j(mass_kg, v_ms):
    return 0.5 * mass_kg * v_ms ** 2


def momentum_kgms(mass_kg, v_ms):
    return mass_kg * v_ms


def arm_first_mode_hz(arm_w_mm, arm_h_mm, arm_len_mm, tip_mass_g, e_pa, rho_petg):
    """Перша згинна власна частота променя (консоль з масою мотора на кінці), Гц.
    Згин у напрямку тяги: глибина = h -> I = w*h^3/12; k = 3EI/L^3;
    m_eff = m_motor + 0.24*m_beam."""
    w = arm_w_mm / 1000.0
    h = arm_h_mm / 1000.0
    L = arm_len_mm / 1000.0
    I = w * h ** 3 / 12.0
    k = 3 * e_pa * I / L ** 3
    m_beam = rho_petg * w * h * L
    m_eff = tip_mass_g / 1000.0 + 0.24 * m_beam
    return (1 / (2 * math.pi)) * math.sqrt(k / m_eff)


def hover_rotation_hz(loaded_rpm_max, thrust_max_per_motor_n, hover_thrust_per_motor_n):
    """Частота обертання на висінні, Гц. Тяга ~ RPM^2 -> rpm_hover = rpm_max*sqrt(T_hover/T_max)."""
    ratio = max(0.0, hover_thrust_per_motor_n / thrust_max_per_motor_n)
    return loaded_rpm_max * math.sqrt(ratio) / 60.0
