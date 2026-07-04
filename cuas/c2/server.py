"""C2-оркестратор: приймає Detection -> фузія 2-з-N -> no-fire -> вогневе рішення ->
чекає на оператора (OK/ABORT) через WS-консоль -> публікує команду ефектору.

Bus створюється лениво у start(), щоб `import cuas.c2.server` не потребував брокера."""
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
current = {"eng": None}
_bus = {"b": None}


def _on_det(js):
    d = Detection.from_json(js)
    trk = fusion.update(d)
    if not trk or in_no_fire(trk.az_deg, NO_FIRE):
        return
    eng = current["eng"]
    if eng is not None and eng.state in ("AWAIT_OK", "LAUNCHED"):
        return  # не затираємо активне заручення (очікує оператора / у польоті)
    sol = firing_solution(trk)
    if sol:
        current["eng"] = Engagement(sol)   # чекає OK у консолі


def start(host="127.0.0.1", port=1883):
    """Під'єднати bus і підписатися на детекції. Викликати перед запуском сервера."""
    b = Bus(host, port)
    b.subscribe(TOPIC_DET, _on_det)
    _bus["b"] = b
    return b


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    while True:
        act = json.loads(await sock.receive_text()).get("action")
        eng = current["eng"]
        if eng and act == "OK":
            eng.operator_ok()
            if _bus["b"]:
                _bus["b"].publish(TOPIC_CMD, json.dumps(eng.command()))
        if eng and act == "ABORT":
            eng.operator_abort()
            if _bus["b"]:
                _bus["b"].publish(TOPIC_CMD, json.dumps(eng.command()))
        await sock.send_text(json.dumps({"state": eng.state if eng else "IDLE",
                                         "sol": eng.sol if eng else None}))


if __name__ == "__main__":
    import uvicorn
    start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
