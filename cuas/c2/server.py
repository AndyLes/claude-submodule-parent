"""C2-оркестратор: Detection -> фузія 2-з-N -> no-fire -> вогневе рішення ->
оператор OK/ABORT/CLEAR (по цілях) через WS-консоль -> команда ефектору.

Заручення тримаються ПО ЦІЛЯХ (bearing-сектор), тож пуск по одній цілі не
робить систему «глухою» до інших. Bus створюється лениво у start(), щоб
`import cuas.c2.server` не потребував брокера."""
import json

from fastapi import FastAPI, WebSocket
from cuas.common.bus import Bus, TOPIC_CMD, TOPIC_DET
from cuas.common.messages import Detection
from cuas.c2.fusion import Fusion
from cuas.c2.engage import firing_solution, in_no_fire
from cuas.c2.engagement import Engagement

app = FastAPI()
fusion = Fusion()
NO_FIRE = [(170, 200)]           # приклад: заборонений сектор (населена зона)
AZ_SECTOR = 15.0                 # ширина сектора цілі для ключа заручення
engagements = {}                 # target_key -> Engagement
_bus = {"b": None}


def target_key(az_deg: float) -> str:
    return str(int((az_deg % 360) // AZ_SECTOR))


def _on_det(js):
    d = Detection.from_json(js)
    trk = fusion.update(d)
    if not trk or in_no_fire(trk.az_deg, NO_FIRE):
        return
    key = target_key(trk.az_deg)
    active = engagements.get(key)
    if active is not None and active.state in ("AWAIT_OK", "LAUNCHED"):
        return  # не затираємо активне заручення по ЦІЙ цілі (інші сектори — вільні)
    sol = firing_solution(trk)
    if sol:
        engagements[key] = Engagement({**sol, "target": key})


def _publish(cmd):
    if _bus["b"] and cmd:
        _bus["b"].publish(TOPIC_CMD, json.dumps(cmd))


def wire(bus):
    """Підписати _on_det на шину (реальну або тестову) і запам'ятати її для публікації."""
    bus.subscribe(TOPIC_DET, _on_det)
    _bus["b"] = bus
    return bus


def start(host="127.0.0.1", port=1883):
    """Створити реальний MQTT-bus і під'єднати оркестратор."""
    return wire(Bus(host, port))


def operator_action(action, key=None):
    """Дія оператора по цілі: OK (пуск), ABORT (скасувати; без id -> усі), CLEAR (прибрати вирішене)."""
    if action == "OK" and key in engagements:
        engagements[key].operator_ok()
        _publish(engagements[key].command())
    elif action == "ABORT":
        for k in ([key] if key in engagements else list(engagements)):
            engagements[k].operator_abort()
            _publish(engagements[k].command())
            del engagements[k]
    elif action == "CLEAR" and key in engagements:
        del engagements[key]


def _state():
    return {"engagements": {k: {"state": e.state, "sol": e.sol} for k, e in engagements.items()}}


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    while True:
        try:
            msg = json.loads(await sock.receive_text())
        except (ValueError, TypeError):
            continue                       # одна зіпсована рамка не має вбивати консоль
        operator_action(msg.get("action"), msg.get("id"))
        await sock.send_text(json.dumps(_state()))


if __name__ == "__main__":
    import uvicorn
    start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
