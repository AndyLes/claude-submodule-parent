def auw_g(components):
    """Повна злітна маса, г."""
    return sum(c["mass_g"] for c in components)


def center_of_mass_mm(components):
    """Центр мас (x, y, z) у мм від центру рами (зважене середнє)."""
    m = auw_g(components)
    return tuple(sum(c["mass_g"] * c[ax] for c in components) / m for ax in ("x_mm", "y_mm", "z_mm"))
