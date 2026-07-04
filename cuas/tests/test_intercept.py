from cuas.sim.intercept import max_engage_range, feasible

def test_faster_interceptor_can_engage_slow_quad():
    assert feasible(v_t=20, v_i=80, latency_s=1.5, detect_rng_m=800) is True

def test_fpv_tight_margin_fails_when_detected_late():
    assert feasible(v_t=45, v_i=55, latency_s=2.0, detect_rng_m=300) is False

def test_max_range_monotonic_in_speed():
    assert max_engage_range(v_t=30, v_i=90, latency_s=1.0) > max_engage_range(v_t=30, v_i=60, latency_s=1.0)
