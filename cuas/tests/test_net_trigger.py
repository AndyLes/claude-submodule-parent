from cuas.effectors.e1_net.mission import should_fire_net


def test_fires_when_centered_and_in_range():
    assert should_fire_net(err_x=0.05, err_y=0.05, rng_m=6.0, max_rng=8.0) is True


def test_no_fire_when_off_center():
    assert should_fire_net(err_x=0.4, err_y=0.0, rng_m=6.0, max_rng=8.0) is False


def test_no_fire_when_too_far():
    assert should_fire_net(0.05, 0.05, rng_m=15.0, max_rng=8.0) is False
