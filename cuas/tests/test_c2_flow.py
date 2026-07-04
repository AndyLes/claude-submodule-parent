from cuas.c2.engagement import Engagement


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
