import pytest
from cuas.c2.dispatch import route


def test_e1_command_goes_to_net_endpoint():
    assert route({"type": "LAUNCH", "effector": "E1"}) == "cuas/effectors/e1_net/cmd"


def test_e2_command_goes_to_ram_endpoint():
    assert route({"type": "LAUNCH", "effector": "E2"}) == "cuas/effectors/e2_ram/cmd"


def test_abort_broadcasts():
    assert route({"type": "ABORT"}) == "cuas/effectors/all/cmd"


def test_route_rejects_unknown_effector():
    with pytest.raises(ValueError):
        route({"type": "LAUNCH", "effector": "E9"})

