def should_fire_net(err_x, err_y, rng_m, max_rng=8.0, center_tol=0.12):
    """Скид сітки лише коли ціль у центрі кадру і в межах дальності сітколета."""
    return (abs(err_x) <= center_tol and abs(err_y) <= center_tol and rng_m <= max_rng)


def net_servo_pwm(fire: bool) -> int:
    return 1900 if fire else 1100   # PWM для сітколета (пружина/CO2)
