from cuas.design.structures import (launch_accel_g, axial_launch_force_n, wing_root_moment_nm,
                                    spar_stress_mpa, max_load_factor, aero_limit_load_factor,
                                    solid_plate_wing_mass_g)


def test_launch_accel_reasonable():
    # ~11 м/с схід з труби 1.2 м -> помірне прискорення (одиниці g), не сотні
    g = launch_accel_g(11.4, 1.2)
    assert 3 < g < 12


def test_axial_force():
    assert axial_launch_force_n(1.183, 5.5) > 0


def test_moment_grows_with_load_factor():
    assert wing_root_moment_nm(1.183, 10, 0.23) > wing_root_moment_nm(1.183, 1, 0.23)


def test_thicker_spar_lower_stress():
    m = wing_root_moment_nm(1.183, 10, 0.23)
    assert spar_stress_mpa(m, 10) < spar_stress_mpa(m, 6)


def test_cf_spar_survives_design_limit():
    # 8мм суцільний CF (150 МПа робоче) має тримати проєктні 10g із запасом
    n_max = max_load_factor(1.183, 0.23, 8.0, 0.0, 150.0)
    assert n_max > 10.0


def test_aero_can_exceed_spar_at_high_speed():
    # на макс. швидкості аеро-перевантаження > межі лонжерона -> кермо ТРЕБА обмежити
    aero = aero_limit_load_factor(55.3, 0.22, 1.05, 1.183)
    spar = max_load_factor(1.183, 0.23, 8.0, 0.0, 150.0)
    assert aero > spar


def test_solid_wing_would_be_too_heavy():
    # суцільна плита ~600 г -> порожнисте+лонжерон обов'язкове (бюджет 180 г)
    assert solid_plate_wing_mass_g(230, 105, 10) > 500
