"""Спрощена 2D-модель прямої зустрічі захисник-в-центрі.
Ціль летить на об'єкт; інтерсептор стартує з центру назустріч.
Консервативно: набір висоти додається окремим членом часу (climb_s)."""
def max_engage_range(v_t: float, v_i: float, latency_s: float, climb_s: float = 0.0) -> float:
    """Максимально корисна дальність (м) за витривалістю інтерсептора."""
    if v_i <= v_t:
        return 0.0
    t_fly_max = 30.0
    R_by_endurance = v_i * t_fly_max / 1.0
    return max(0.0, R_by_endurance)

def feasible(v_t: float, v_i: float, latency_s: float, detect_rng_m: float, climb_s: float = 0.0) -> bool:
    """Чи встигаємо перехопити на безпечній відстані, якщо ціль виявлена на detect_rng_m."""
    if v_i <= v_t:
        return False
    d_safe = 50.0
    t_react = latency_s + climb_s
    remaining = detect_rng_m - v_t * t_react
    if remaining <= d_safe:
        return False
    t_fly = remaining / (v_i + v_t)
    d_intercept = v_i * t_fly
    return d_intercept >= d_safe and (v_i / v_t) >= 1.25  # явна вимога маржі 25%
