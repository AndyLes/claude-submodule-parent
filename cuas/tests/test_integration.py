"""Software-in-the-loop: проганяємо повний конвеєр detection -> фузія -> оператор
OK -> маршрутизація на ефектор через синхронну in-memory шину (без брокера/заліза)."""
import json

from cuas.c2 import server, dispatch
from cuas.c2.fusion import Fusion
from cuas.common.bus import TOPIC_DET
from cuas.common.messages import Detection


class FakeBus:
    """Синхронна in-memory заміна Bus (той самий інтерфейс publish/subscribe)."""

    def __init__(self):
        self._subs = {}

    def publish(self, topic, payload):
        for cb in list(self._subs.get(topic, [])):
            cb(payload)

    def subscribe(self, topic, cb):
        self._subs.setdefault(topic, []).append(cb)


def _wire_fresh():
    bus = FakeBus()
    server.engagements.clear()
    server.fusion = Fusion(az_gate_deg=12, t_gate_s=5.0)
    server.wire(bus)
    dispatch.wire_dispatcher(bus)
    captured = []
    for name, topic in [("e1", "cuas/effectors/e1_net/cmd"),
                        ("e2", "cuas/effectors/e2_ram/cmd"),
                        ("all", "cuas/effectors/all/cmd")]:
        bus.subscribe(topic, (lambda n: lambda js: captured.append((n, json.loads(js))))(name))
    return bus, captured


def test_quad_end_to_end_routes_launch_to_net():
    bus, captured = _wire_fresh()
    bus.publish(TOPIC_DET, Detection("acoustic", 130.0, 0.8, 1000.0, cls="quad").to_json())
    bus.publish(TOPIC_DET, Detection("eoir", 131.0, 0.9, 1001.0, cls="quad").to_json())
    key = server.target_key(130.5)
    assert key in server.engagements                      # detection -> фузія -> заручення
    server.operator_action("OK", key)                     # оператор погоджує
    assert captured == [("e1", {"type": "LAUNCH", "effector": "E1",
                                "launch_az": server.engagements[key].sol["launch_az"],
                                "cls": "quad", "target": key})]


def test_abort_without_id_broadcasts_and_frees_slots():
    bus, captured = _wire_fresh()
    bus.publish(TOPIC_DET, Detection("acoustic", 50.0, 0.8, 1000.0, cls="fpv").to_json())
    bus.publish(TOPIC_DET, Detection("eoir", 51.0, 0.9, 1001.0, cls="fpv").to_json())
    assert server.engagements                             # є ціль
    server.operator_action("ABORT")                       # паніка: без id
    assert ("all", {"type": "ABORT"}) in captured
    assert server.engagements == {}                       # слот звільнено
