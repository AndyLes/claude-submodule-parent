from cuas.c2.engage import select_effector, in_no_fire
from cuas.common.messages import Track


def _trk(cls, az):
    return Track("t", az, 5.0, 600.0, cls, 0.8, ["eoir", "acoustic"], 1.0)


def test_quad_selects_e1_net():
    assert select_effector(_trk("quad", 100)) == "E1"


def test_fpv_selects_e2_ram():
    assert select_effector(_trk("fpv", 100)) == "E2"


def test_fixedwing_deferred_phase3():
    assert select_effector(_trk("fixedwing", 100)) is None  # E3 не в Phase 1


def test_no_fire_arc_blocks():
    assert in_no_fire(az_deg=185, arcs=[(170, 200)]) is True
    assert in_no_fire(az_deg=100, arcs=[(170, 200)]) is False
