import paho.mqtt.client as mqtt

TOPIC_DET = "cuas/detections"
TOPIC_TRK = "cuas/tracks"
TOPIC_CMD = "cuas/commands"

class Bus:
    def __init__(self, host="127.0.0.1", port=1883):
        self.c = mqtt.Client()
        self.c.connect(host, port, 60)
    def publish(self, topic: str, payload: str): self.c.publish(topic, payload)
    def subscribe(self, topic: str, cb):
        self.c.subscribe(topic); self.c.message_callback_add(topic, lambda cl, u, m: cb(m.payload.decode()))
    def loop_forever(self): self.c.loop_forever()
