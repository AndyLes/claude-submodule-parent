import time
import argparse

from cuas.common.bus import Bus, TOPIC_DET
from cuas.common.messages import Detection
from cuas.sensors.acoustic.classify import drone_score


def run(bearing_deg: float, sr=16000, win_s=1.0, thr=0.6):
    import sounddevice as sd  # lazy: hardware/heavy dep, only needed when the daemon runs

    bus = Bus()
    while True:
        rec = sd.rec(int(win_s * sr), samplerate=sr, channels=1, dtype="float32")
        sd.wait()
        s = drone_score(rec[:, 0], sr)
        if s >= thr:
            d = Detection(source="acoustic", az_deg=bearing_deg, conf=float(s), t_unix=time.time())
            bus.publish(TOPIC_DET, d.to_json())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bearing", type=float, required=True)
    run(ap.parse_args().bearing)
