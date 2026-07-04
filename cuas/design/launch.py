"""Енергетика тубусного старту E3 + порівняння методів.

Ключ: планер витримує проєктні 10 g (лонжерон ~14 g). Метод старту не має
перевищити це. Пневматика дає ПОСТІЙНУ силу (пік = середнє), бунджі — спадну
(пік ~1.8x середнього), тож при однаковій швидкості сходу бунджі б'є вищим g."""
import math

G = 9.80665


def launch_energy_j(m_kg, v_exit_ms):
    return 0.5 * m_kg * v_exit_ms ** 2


def required_force_n(m_kg, v_exit_ms, tube_len_m):
    """Середня сила для сходу v_exit на довжині tube_len (рівноприскорено)."""
    return m_kg * v_exit_ms ** 2 / (2 * tube_len_m)


def launch_accel_g(v_exit_ms, tube_len_m):
    return v_exit_ms ** 2 / (2 * tube_len_m) / G


def pneumatic_pressure_bar(force_n, bore_mm, piston_eff=0.85):
    """Тиск для сили force_n на поршень діаметром bore_mm (бар)."""
    area_m2 = math.pi * (bore_mm / 1000.0 / 2.0) ** 2
    return force_n / (area_m2 * piston_eff) / 1e5


def bungee_peak_g(avg_g, force_shape=1.8):
    """Пік g для бунджі: сила спадає по ходу, тож пік вищий за середнє."""
    return avg_g * force_shape


def exit_speed_ms(force_n, tube_len_m, m_kg):
    return math.sqrt(2 * force_n * tube_len_m / m_kg)


def wing_deploy_margin_ok(v_exit_ms, stall_ms, min_ratio=1.35):
    """Схід має бути з запасом над зривом — крило розкривається/мотор розкручується
    вже в повітрі, тож не можна сходити на межі зриву."""
    return v_exit_ms >= stall_ms * min_ratio
