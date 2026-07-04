from cuas.c2.engagement import Engagement
from cuas.c2 import server
from cuas.c2.fusion import Fusion
from cuas.common.messages import Detection


def test_requires_ok_before_launch():
    e = Engagement(solution={"effector": "E2", "launch_az": 100, "cls": "fpv"})
    assert e.state == "AWAIT_OK"
    assert e.command() is None
    e.operator_ok()
    assert e.state == "LAUNCHED"
    assert e.command()["effector"] == "E2"


def test_abort_stops_before_hit():
    e = Engagement(solution={"effector": "E2", "launch_az": 100, "cls": "fpv"})
    e.operator_ok()
    e.operator_abort()
    assert e.state == "ABORTED"
    assert e.command()["type"] == "ABORT"


def test_on_det_does_not_clobber_active_engagement():
    server.fusion = Fusion(az_gate_deg=12, t_gate_s=5.0)
    launched = Engagement({"effector": "E2", "launch_az": 100, "cls": "fpv"})
    launched.operator_ok()  # LAUNCHED
    server.current["eng"] = launched
    server._on_det(Detection("acoustic", 130.0, 0.8, 1000.0, cls="quad").to_json())
    server._on_det(Detection("rf", 132.0, 0.8, 1001.0).to_json())
    assert server.current["eng"] is launched  # активне заручення не затерте


def test_on_det_creates_engagement_when_idle():
    server.fusion = Fusion(az_gate_deg=12, t_gate_s=5.0)
    server.current["eng"] = None
    server._on_det(Detection("acoustic", 130.0, 0.8, 2000.0, cls="quad").to_json())
    server._on_det(Detection("rf", 132.0, 0.8, 2001.0).to_json())
    assert server.current["eng"] is not None
    assert server.current["eng"].sol["effector"] == "E1"
