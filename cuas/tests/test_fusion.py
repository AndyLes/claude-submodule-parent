from cuas.c2.fusion import Fusion
from cuas.common.messages import Detection


def test_two_sources_same_bearing_confirm():
    f = Fusion(az_gate_deg=12, t_gate_s=2.0)
    assert f.update(Detection("acoustic", 130.0, 0.7, 1000.0)) is None
    trk = f.update(Detection("rf", 134.0, 0.7, 1001.0))
    assert trk is not None and set(trk.sources) == {"acoustic", "rf"}


def test_single_source_no_confirm():
    f = Fusion(12, 2.0)
    assert f.update(Detection("acoustic", 130.0, 0.7, 1000.0)) is None


def test_far_bearing_not_fused():
    f = Fusion(12, 2.0)
    f.update(Detection("acoustic", 130.0, 0.7, 1000.0))
    assert f.update(Detection("rf", 200.0, 0.7, 1000.5)) is None
