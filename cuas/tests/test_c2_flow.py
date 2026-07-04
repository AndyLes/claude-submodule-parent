import pytest
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


@pytest.fixture(autouse=True)
def _reset_server_state():
    """Не лишати мутований глобальний стан server між тестами."""
    yield
    server.engagements.clear()
    server.fusion = Fusion()


def _confirm(az, cls="quad", t=1000.0):
    # два РІЗНІ джерела в одному азимуті -> підтверджений (2-з-N) трек
    server._on_det(Detection("acoustic", az, 0.8, t, cls=cls).to_json())
    server._on_det(Detection("rf", az + 2.0, 0.8, t + 1.0).to_json())


def test_on_det_creates_engagement_when_idle():
    server.fusion = Fusion(az_gate_deg=12, t_gate_s=5.0)
    _confirm(130.0, cls="quad")
    key = server.target_key(130.0)
    assert key in server.engagements
    assert server.engagements[key].sol["effector"] == "E1"


def test_on_det_does_not_clobber_active_same_target():
    server.fusion = Fusion(az_gate_deg=12, t_gate_s=5.0)
    key = server.target_key(130.0)
    launched = Engagement({"effector": "E2", "launch_az": 130, "cls": "fpv", "target": key})
    launched.operator_ok()  # LAUNCHED
    server.engagements[key] = launched
    _confirm(130.0, cls="quad")
    assert server.engagements[key] is launched  # та сама ціль -> не затерто


def test_launched_target_does_not_block_other_targets():
    # регресія #1: постріл по одній цілі не робить систему глухою до інших
    server.fusion = Fusion(az_gate_deg=12, t_gate_s=5.0)
    k1 = server.target_key(40.0)
    e1 = Engagement({"effector": "E2", "launch_az": 40, "cls": "fpv", "target": k1})
    e1.operator_ok()  # LAUNCHED
    server.engagements[k1] = e1
    _confirm(130.0, cls="quad")            # інша ціль, інший сектор
    k2 = server.target_key(130.0)
    assert k2 != k1
    assert k2 in server.engagements        # нова ціль отримала своє заручення
