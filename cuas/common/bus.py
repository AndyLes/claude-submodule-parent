import paho.mqtt.client as mqtt

TOPIC_DET = "cuas/detections"
TOPIC_TRK = "cuas/tracks"
TOPIC_CMD = "cuas/commands"


def _new_client():
    # paho-mqtt 2.x вимагає явну версію callback-API; 1.x її не має
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        return mqtt.Client()


class Bus:
    def __init__(self, host="127.0.0.1", port=1883):
        self.c = _new_client()
        self.c.connect(host, port, 60)
    def publish(self, topic: str, payload: str): self.c.publish(topic, payload)
    def subscribe(self, topic: str, cb):
        self.c.subscribe(topic); self.c.message_callback_add(topic, lambda cl, u, m: cb(m.payload.decode()))
    def loop_forever(self): self.c.loop_forever()
