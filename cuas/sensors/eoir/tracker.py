import time

from cuas.common.bus import Bus, TOPIC_TRK, TOPIC_DET
from cuas.common.messages import Track, Detection
from cuas.sensors.eoir.ptz import PTZ

CLASS_MAP = {0: "quad", 1: "fpv", 2: "fixedwing", 3: "bird"}


def pixel_to_azel(cx, cy, W, H, ptz_az, ptz_el, hfov, vfov):
    az = ptz_az + (cx - W / 2) / (W / 2) * (hfov / 2)
    el = ptz_el - (cy - H / 2) / (H / 2) * (vfov / 2)
    return az % 360, el


def run(model_path="cuas/sensors/eoir/uav_yolo.pt"):
    from ultralytics import YOLO  # lazy: heavy dep, only when the tracker daemon runs

    model = YOLO(model_path)
    ptz = PTZ()
    bus = Bus()
    # cue: коли приходить Detection з азимутом — навести PTZ
    bus.subscribe(TOPIC_DET, lambda js: ptz.slew_to(Detection.from_json(js).az_deg))
    for r in model.track(source=ptz.stream_url(), stream=True, persist=True, verbose=False):
        if r.boxes is None or len(r.boxes) == 0:
            continue
        b = r.boxes[int(r.boxes.conf.argmax())]
        cx, cy = map(float, b.xywh[0][:2])
        conf = float(b.conf[0])
        cls = CLASS_MAP.get(int(b.cls[0]), "unknown")
        if cls == "bird" or conf < 0.5:
            continue
        az, el = pixel_to_azel(cx, cy, r.orig_shape[1], r.orig_shape[0], ptz.az, ptz.el, ptz.hfov, ptz.vfov)
        ptz.center_on(cx, cy)  # тримати ціль у центрі (замкнений трек)
        bus.publish(
            TOPIC_TRK,
            Track(track_id=f"eo{int(b.id or 0)}", az_deg=az, el_deg=el, rng_m=-1.0,
                  cls=cls, conf=conf, sources=["eoir"], t_unix=time.time()).to_json(),
        )
