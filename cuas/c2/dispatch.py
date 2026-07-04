import json

from cuas.common.bus import TOPIC_CMD

_ENDPOINTS = {"E1": "cuas/effectors/e1_net/cmd", "E2": "cuas/effectors/e2_ram/cmd"}


def route(cmd: dict) -> str:
    """Маршрут команди C2 до топіка потрібного ефектора (ABORT — усім).
    Невідомий/відсутній ефектор -> явна помилка (fail-safe: не стріляти навмання)."""
    if cmd.get("type") == "ABORT":
        return "cuas/effectors/all/cmd"
    eff = cmd.get("effector")
    if eff not in _ENDPOINTS:
        raise ValueError(f"route: unknown/missing effector {eff!r} in {cmd!r}")
    return _ENDPOINTS[eff]


def wire_dispatcher(bus):
    """Підписатися на TOPIC_CMD і маршрутизувати кожну команду C2 на топік ефектора."""
    def _route_cmd(js):
        bus.publish(route(json.loads(js)), js)
    bus.subscribe(TOPIC_CMD, _route_cmd)
    return _route_cmd
