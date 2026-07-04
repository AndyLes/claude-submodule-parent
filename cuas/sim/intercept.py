"""Спрощена 2D-модель прямої зустрічі захисник-в-центрі.
Ціль летить на об'єкт; інтерсептор стартує з центру назустріч.
Консервативно: набір висоти додається окремим членом часу (climb_s)."""
def max_engage_range(v_t: float, v_i: float, latency_s: float, climb_s: float = 0.0) -> float:
    """Максимально корисна дальність цілі (м) на момент виявлення, за якої ще
    встигаємо перехопити в межах витривалості інтерсептора (t_fly_max).
    Враховує реакцію: за t_react ціль зближується, далі закриваємо (v_i+v_t)."""
    if v_i <= v_t:
        return 0.0
    t_fly_max = 30.0
    t_react = latency_s + climb_s
    return max(0.0, v_t * t_react + t_fly_max * (v_i + v_t))

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
    # v_t<=0 (зависання/стаціонарна ціль) -> маржа нескінченна; інакше вимога 25%
    margin_ok = v_t <= 0 or (v_i / v_t) >= 1.25
    return d_intercept >= d_safe and margin_ok
