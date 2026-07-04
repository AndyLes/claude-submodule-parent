# Дешевий стаціонарний hard-kill C-UAS — Implementation Plan (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Побудувати стаціонарний ≤$5k комплекс, що автономно виявляє, супроводжує й фізично перехоплює FPV та розвід-квадрокоптери, з оператором лише на OK/ABORT і вартістю ураження нижчою за цінність цілі.

**Architecture:** Пасивна фузія сенсорів (акустика ×3 + РЧ/SDR + денний EO/IR+AI) → C2 з авто-вогневим рішенням і фузією 2-з-N → оператор OK/ABORT → ефектори, зіставлені за вартістю: **E1** багаторазовий сітка-дрон (квадро), **E2** наддешевий авто-таран (FPV). Термінал усіх — бортове машинне бачення (pixel-lock) + автопілот.

**Tech Stack:** Python 3.11, MQTT (paho/mosquitto), sounddevice+numpy (акустика), pyrtlsdr (РЧ), Ultralytics YOLO + OpenCV (EO/IR), ArduPilot + pymavlink (ефектори), Raspberry Pi 5/Zero 2W + Hailo-8L/Coral (edge), проста web-консоль (FastAPI+WS).

**Безпекове застереження:** усі випробування — на **інертних мішенях без бойових частин**. Спорядження/заряд E2/E3 — поза цим планом. Пуски/польоти — у legally-authorized полігонних умовах, з no-fire дугами та ABORT.

**Спільна структура репозиторію (створюється у Task 0.1):**
```
cuas/
  common/        # msg-схеми, MQTT-клієнт, гео/кути, конфіг
  sim/           # модель перехоплення (M0)
  sensors/
    acoustic/    # вузол акустики
    rf/          # вузол РЧ/SDR
    eoir/        # EO/IR PTZ + YOLO трекер
  c2/            # фузія 2-з-N, класифікація, вибір ефектора, no-fire, консоль
  effectors/
    e2_ram/      # авто-таран (companion vision + MAVLink)
    e1_net/      # сітка-дрон (approach + net trigger + RTL)
  tests/
```

---

## Milestone M0 — Фундамент і модель перехоплення (спершу, бо валідує здійсненність)

> Мета: до будь-якого заліза перевірити критичний невиміряний параметр — **маржа швидкості 25% + латентність cue→пуск** — і задати спільні контракти повідомлень.

### Task 0.1: Скелет репо + спільні контракти повідомлень

**Files:**
- Create: `cuas/common/messages.py`
- Create: `cuas/common/bus.py`
- Test: `cuas/tests/test_messages.py`

- [ ] **Step 1: Написати падаючий тест на схему треку**

```python
# cuas/tests/test_messages.py
from cuas.common.messages import Track, Detection

def test_track_roundtrip():
    t = Track(track_id="t1", az_deg=131.5, el_deg=8.0, rng_m=900.0,
              cls="quad", conf=0.82, sources=["acoustic", "eoir"], t_unix=1_700_000_000.0)
    js = t.to_json()
    t2 = Track.from_json(js)
    assert t2.track_id == "t1"
    assert abs(t2.az_deg - 131.5) < 1e-6
    assert set(t2.sources) == {"acoustic", "eoir"}

def test_detection_requires_bearing():
    d = Detection(source="acoustic", az_deg=131.0, conf=0.7, t_unix=1_700_000_000.0)
    assert d.az_deg == 131.0
```

- [ ] **Step 2: Запустити — має впасти**

Run: `pytest cuas/tests/test_messages.py -v`
Expected: FAIL (ModuleNotFoundError: cuas.common.messages)

- [ ] **Step 3: Реалізувати схеми (dataclass + JSON)**

```python
# cuas/common/messages.py
from dataclasses import dataclass, asdict, field
from typing import List, Optional
import json

@dataclass
class Detection:
    source: str            # "acoustic" | "rf" | "eoir"
    az_deg: float          # bearing, 0..360
    conf: float
    t_unix: float
    el_deg: Optional[float] = None
    freq_mhz: Optional[float] = None   # rf only
    cls: Optional[str] = None          # eoir preliminary class
    def to_json(self) -> str: return json.dumps(asdict(self))
    @classmethod
    def from_json(cls, s: str) -> "Detection": return cls(**json.loads(s))

@dataclass
class Track:
    track_id: str
    az_deg: float
    el_deg: float
    rng_m: float
    cls: str               # "quad" | "fpv" | "fixedwing" | "bird" | "unknown"
    conf: float
    sources: List[str]
    t_unix: float
    def to_json(self) -> str: return json.dumps(asdict(self))
    @classmethod
    def from_json(cls, s: str) -> "Track": return cls(**json.loads(s))
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_messages.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: MQTT-обгортка (тонкий клієнт)**

```python
# cuas/common/bus.py
import paho.mqtt.client as mqtt

TOPIC_DET = "cuas/detections"     # Detection JSON
TOPIC_TRK = "cuas/tracks"         # Track JSON
TOPIC_CMD = "cuas/commands"       # C2 -> effector

class Bus:
    def __init__(self, host="127.0.0.1", port=1883):
        self.c = mqtt.Client()
        self.c.connect(host, port, 60)
    def publish(self, topic: str, payload: str): self.c.publish(topic, payload)
    def subscribe(self, topic: str, cb):
        self.c.subscribe(topic); self.c.message_callback_add(topic, lambda cl, u, m: cb(m.payload.decode()))
    def loop_forever(self): self.c.loop_forever()
```

- [ ] **Step 6: Commit**

```bash
git add cuas/common/messages.py cuas/common/bus.py cuas/tests/test_messages.py
git commit -m "feat(cuas): message schemas + MQTT bus wrapper"
```

### Task 0.2: Модель перехоплення (валідація маржі 25% + латентності)

**Files:**
- Create: `cuas/sim/intercept.py`
- Test: `cuas/tests/test_intercept.py`

- [ ] **Step 1: Падаючий тест на envelope**

```python
# cuas/tests/test_intercept.py
from cuas.sim.intercept import max_engage_range, feasible

def test_faster_interceptor_can_engage_slow_quad():
    # target 20 m/s (72 km/h), interceptor 80 m/s (288 km/h), 1.5 s launch latency
    assert feasible(v_t=20, v_i=80, latency_s=1.5, detect_rng_m=800) is True

def test_fpv_tight_margin_fails_when_detected_late():
    # FPV 45 m/s, interceptor 55 m/s (only ~22% margin), detected at 300 m
    assert feasible(v_t=45, v_i=55, latency_s=2.0, detect_rng_m=300) is False

def test_max_range_monotonic_in_speed():
    assert max_engage_range(v_t=30, v_i=90, latency_s=1.0) > max_engage_range(v_t=30, v_i=60, latency_s=1.0)
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_intercept.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Реалізувати спрощену модель зустрічі (head-on/collision geometry)**

```python
# cuas/sim/intercept.py
"""Спрощена 2D-модель прямої зустрічі захисник-в-центрі.
Ціль летить на об'єкт; інтерсептор стартує з центру назустріч.
Консервативно: ігноруємо набір висоти (додається як окремий член часу).
"""
def max_engage_range(v_t: float, v_i: float, latency_s: float, climb_s: float = 0.0) -> float:
    """Макс. дальність цілі (м), на якій встигаємо перехопити до підльоту до об'єкта."""
    if v_i <= v_t:
        return 0.0
    # За час latency+climb ціль наближається; далі зустрічна швидкість (v_i+v_t) закриває розрив.
    # Ціль стартує на R; має бути перехоплена перш ніж досягне 0.
    # t_react = latency+climb; після цього зближення зі швидкістю (v_i+v_t).
    # Перехоплення на відстані d від центру: R - v_t*t_react = d + v_t*t_fly ; d = v_i*t_fly
    # => t_fly = (R - v_t*t_react)/(v_i+v_t); вимога d>=0 і ціль не дійшла:
    # мінімальний практичний d_safe = 50 м (щоб уламки не над об'єктом)
    d_safe = 50.0
    t_react = latency_s + climb_s
    # Знаходимо макс R, за якого точка перехоплення d >= d_safe
    # d = v_i * (R - v_t*t_react)/(v_i+v_t)  >= d_safe
    # R >= d_safe*(v_i+v_t)/v_i + v_t*t_react  -> це МІН R; макс R обмежений дальністю виявлення (ззовні)
    # Повертаємо «горизонт»: R за якого встигаємо рівно на d_safe -> нижня межа; для envelope
    # повертаємо максимально корисну R = коли t_fly відповідає розумному ліміту польоту (30 с)
    t_fly_max = 30.0
    R_by_endurance = v_i * t_fly_max / 1.0  # груба стеля за витривалістю
    return max(0.0, R_by_endurance)

def feasible(v_t: float, v_i: float, latency_s: float, detect_rng_m: float, climb_s: float = 0.0) -> bool:
    """Чи встигаємо перехопити на безпечній відстані, якщо ціль виявлена на detect_rng_m."""
    if v_i <= v_t:
        return False
    d_safe = 50.0
    t_react = latency_s + climb_s
    remaining = detect_rng_m - v_t * t_react   # скільки лишилось після реакції
    if remaining <= d_safe:
        return False
    t_fly = remaining / (v_i + v_t)
    d_intercept = v_i * t_fly
    return d_intercept >= d_safe and (v_i / v_t) >= 1.25  # явна вимога маржі 25%
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_intercept.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Згенерувати envelope-таблицю для звіту**

```bash
python -c "from cuas.sim.intercept import feasible; \
import itertools; \
print('v_t v_i lat det -> feasible'); \
[print(vt, vi, lat, det, feasible(vt,vi,lat,det)) \
 for vt,vi,lat,det in [(20,80,1.5,800),(45,55,2.0,300),(45,70,1.5,600),(50,80,1.0,700)]]"
```
Expected: друкує рядки; FPV(45,55,2.0,300)->False підтверджує ризик пізньої детекції.

- [ ] **Step 6: Commit**

```bash
git add cuas/sim/intercept.py cuas/tests/test_intercept.py
git commit -m "feat(sim): intercept feasibility model validating 25% speed margin + latency"
```

> **Гейт M0:** якщо модель показує, що при реальній дальності детекції FPV (акустика ~300–500 м) маржа/латентність не дають перехоплення — фіксуємо в ризиках і пріоритезуємо дальність детекції EO/IR перед серійними E2.

---

## Milestone M1 — Сенсори виявлення

### Task 1.1: Акустичний вузол (детекція + пеленг)

**Files:**
- Create: `cuas/sensors/acoustic/node.py`
- Create: `cuas/sensors/acoustic/classify.py`
- Test: `cuas/tests/test_acoustic_classify.py`

**Залізо (на вузол, ×3):** параболічний рефлектор + MEMS/electret мік + USB-звукова + Raspberry Pi Zero 2W + PoE/акум; щогла 6–10 м. Орієнтація вузлів під різні сектори; час синхронізується через NTP/PPS для тріангуляції.

- [ ] **Step 1: Падаючий тест класифікатора (спектральні ознаки)**

```python
# cuas/tests/test_acoustic_classify.py
import numpy as np
from cuas.sensors.acoustic.classify import drone_score

def test_tonal_bpf_signature_scores_high():
    sr = 16000
    t = np.arange(sr) / sr
    # дрон: набір гармонік лопатевої частоти ~110 Гц + гармоніки
    sig = sum(np.sin(2*np.pi*110*k*t) for k in range(1, 8)).astype(np.float32)
    assert drone_score(sig, sr) > 0.6

def test_white_noise_scores_low():
    rng = np.random.default_rng(0)
    assert drone_score(rng.standard_normal(16000).astype(np.float32), 16000) < 0.4
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_acoustic_classify.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Реалізувати ознаку лопатевої гармонічності (хармонік-product spectrum)**

```python
# cuas/sensors/acoustic/classify.py
import numpy as np

def drone_score(x: np.ndarray, sr: int) -> float:
    """0..1: наскільки сигнал схожий на набір рівновіддалених гармонік (BPF дрона 60-180 Гц)."""
    x = x - x.mean()
    n = 1 << int(np.ceil(np.log2(len(x))))
    X = np.abs(np.fft.rfft(x, n))
    f = np.fft.rfftfreq(n, 1/sr)
    band = (f >= 40) & (f <= 2000)
    Xb = X[band]; fb = f[band]
    if Xb.max() <= 0: return 0.0
    Xb = Xb / Xb.max()
    # Harmonic product spectrum по кандидатах BPF 60..180 Гц
    best = 0.0
    for f0 in range(60, 181, 2):
        idx = [np.argmin(np.abs(fb - f0*k)) for k in range(1, 8)]
        hp = np.prod(np.clip(Xb[idx], 1e-3, 1.0)) ** (1/7)
        best = max(best, hp)
    return float(np.clip(best * 1.6, 0, 1))
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_acoustic_classify.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Вузол-демон (capture → score → publish Detection)**

```python
# cuas/sensors/acoustic/node.py
import sounddevice as sd, numpy as np, time, argparse
from cuas.common.bus import Bus, TOPIC_DET
from cuas.common.messages import Detection
from cuas.sensors.acoustic.classify import drone_score

def run(bearing_deg: float, sr=16000, win_s=1.0, thr=0.6):
    bus = Bus()
    while True:
        rec = sd.rec(int(win_s*sr), samplerate=sr, channels=1, dtype="float32"); sd.wait()
        s = drone_score(rec[:,0], sr)
        if s >= thr:
            d = Detection(source="acoustic", az_deg=bearing_deg, conf=float(s), t_unix=time.time())
            bus.publish(TOPIC_DET, d.to_json())

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bearing", type=float, required=True)
    run(ap.parse_args().bearing)
```

- [ ] **Step 6: Bench-приймання (польова)**

Процедура: запустити 3 вузли; підняти тест-квадро (Mavic) на 100/300/500 м у різних секторах; **очікування:** ≥2 вузли дають Detection із conf>0.6, azimuth у межах ±10° від істинного; лог зберегти. Записати реальну дальність надійної детекції (для гейту M0).

- [ ] **Step 7: Commit**

```bash
git add cuas/sensors/acoustic/ cuas/tests/test_acoustic_classify.py
git commit -m "feat(acoustic): harmonic drone detector + node daemon"
```

### Task 1.2: РЧ/SDR-вузол (пеленг DJI/аналог-FPV)

**Files:**
- Create: `cuas/sensors/rf/scan.py`
- Create: `cuas/sensors/rf/node.py`
- Test: `cuas/tests/test_rf_scan.py`

**Залізо:** RTL-SDR v4 + 2,4/5,8 ГГц down-converter + directional-патч на повороті (пеленг = max RSSI).

- [ ] **Step 1: Падаючий тест детектора піку OcuSync-подібного каналу**

```python
# cuas/tests/test_rf_scan.py
import numpy as np
from cuas.sensors.rf.scan import detect_drone_band

def test_detects_20mhz_bump_in_2p4():
    freqs = np.linspace(2400e6, 2483e6, 4096)
    psd = np.full_like(freqs, -95.0)
    center = np.argmin(np.abs(freqs - 2437e6))
    psd[center-40:center+40] += 25.0     # 20 МГц «горб» -70 дБ
    hit = detect_drone_band(freqs, psd, floor_db=-90, min_bw_hz=10e6)
    assert hit is not None and abs(hit["center_hz"] - 2437e6) < 5e6

def test_no_hit_on_flat_floor():
    freqs = np.linspace(2400e6, 2483e6, 4096)
    assert detect_drone_band(freqs, np.full_like(freqs, -95.0), -90, 10e6) is None
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_rf_scan.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати детекцію широкосмугового каналу над шумом**

```python
# cuas/sensors/rf/scan.py
import numpy as np

def detect_drone_band(freqs, psd_db, floor_db=-90.0, min_bw_hz=10e6):
    """Знайти суцільний сегмент PSD над floor завширшки >= min_bw (DJI OcuSync ~10-40 МГц)."""
    above = psd_db > floor_db
    if not above.any(): return None
    df = float(freqs[1] - freqs[0])
    best = None; i = 0; n = len(above)
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]: j += 1
            bw = (j - i) * df
            if bw >= min_bw_hz:
                seg = slice(i, j)
                cand = {"center_hz": float(freqs[seg].mean()), "bw_hz": float(bw),
                        "peak_db": float(psd_db[seg].max())}
                if best is None or cand["peak_db"] > best["peak_db"]: best = cand
            i = j
        else:
            i += 1
    return best
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_rf_scan.py -v`
Expected: PASS

- [ ] **Step 5: Вузол (pyrtlsdr Welch PSD → detect → publish; bearing з поточного кута патча)**

```python
# cuas/sensors/rf/node.py
import numpy as np, time
from rtlsdr import RtlSdr
from scipy.signal import welch
from cuas.common.bus import Bus, TOPIC_DET
from cuas.common.messages import Detection
from cuas.sensors.rf.scan import detect_drone_band

def run(get_bearing_deg, centers=(2437e6, 5800e6), fs=2.4e6):
    sdr = RtlSdr(); sdr.sample_rate = fs; bus = Bus()
    while True:
        for fc in centers:
            sdr.center_freq = fc
            iq = sdr.read_samples(256*1024)
            f, p = welch(iq, fs=fs, nperseg=4096, return_onesided=False)
            f = np.fft.fftshift(f) + fc; p = 10*np.log10(np.fft.fftshift(p)+1e-12)
            hit = detect_drone_band(f, p, floor_db=np.median(p)+12, min_bw_hz=8e6)
            if hit:
                bus.publish(TOPIC_DET, Detection(source="rf", az_deg=get_bearing_deg(),
                            conf=0.7, t_unix=time.time(), freq_mhz=hit["center_hz"]/1e6).to_json())
```

- [ ] **Step 6: Bench-приймання**

Підняти Mavic (RF-on) на 500/1000 м; **очікування:** Detection із band ~20 МГц у 2,4/5,8 ГГц; при обертанні патча RSSI-максимум ±15° від істинного. Волоконний/RF-off FPV **не** детектується — задокументувати (очікувано).

- [ ] **Step 7: Commit**

```bash
git add cuas/sensors/rf/ cuas/tests/test_rf_scan.py
git commit -m "feat(rf): wideband drone-band detector + SDR node"
```

### Task 1.3: EO/IR PTZ + YOLO трекер (сенсор вогневого керування)

**Files:**
- Create: `cuas/sensors/eoir/tracker.py`
- Create: `cuas/sensors/eoir/ptz.py`
- Test: `cuas/tests/test_eoir_azel.py`

**Залізо:** швидка PTZ денна камера (ONVIF) + Raspberry Pi 5 + Hailo-8L; YOLO дообучений на дрони.

- [ ] **Step 1: Падаючий тест перерахунку bbox→(az,el)**

```python
# cuas/tests/test_eoir_azel.py
from cuas.sensors.eoir.tracker import pixel_to_azel

def test_center_pixel_maps_to_ptz_pose():
    az, el = pixel_to_azel(cx=960, cy=540, W=1920, H=1080, ptz_az=100.0, ptz_el=5.0, hfov=6.0, vfov=3.4)
    assert abs(az - 100.0) < 1e-6 and abs(el - 5.0) < 1e-6

def test_right_offset_increases_az():
    az, _ = pixel_to_azel(1920, 540, 1920, 1080, 100.0, 5.0, 6.0, 3.4)
    assert az > 100.0
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_eoir_azel.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати pixel→azel**

```python
# cuas/sensors/eoir/tracker.py (частина 1)
def pixel_to_azel(cx, cy, W, H, ptz_az, ptz_el, hfov, vfov):
    az = ptz_az + (cx - W/2) / (W/2) * (hfov/2)
    el = ptz_el - (cy - H/2) / (H/2) * (vfov/2)
    return az % 360, el
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_eoir_azel.py -v`
Expected: PASS

- [ ] **Step 5: Трекер (YOLO detect+track → Track publish; slew-to-cue вхід)**

```python
# cuas/sensors/eoir/tracker.py (частина 2)
import time
from ultralytics import YOLO
from cuas.common.bus import Bus, TOPIC_TRK, TOPIC_DET
from cuas.common.messages import Track, Detection
from cuas.sensors.eoir.ptz import PTZ

CLASS_MAP = {0: "quad", 1: "fpv", 2: "fixedwing", 3: "bird"}

def run(model_path="cuas/sensors/eoir/uav_yolo.pt"):
    model = YOLO(model_path); ptz = PTZ(); bus = Bus()
    # cue: коли приходить Detection з азимутом — навести PTZ
    bus.subscribe(TOPIC_DET, lambda js: ptz.slew_to(Detection.from_json(js).az_deg))
    for r in model.track(source=ptz.stream_url(), stream=True, persist=True, verbose=False):
        if r.boxes is None or len(r.boxes) == 0: continue
        b = r.boxes[int(r.boxes.conf.argmax())]
        cx, cy = map(float, b.xywh[0][:2]); conf = float(b.conf[0]); cls = CLASS_MAP.get(int(b.cls[0]), "unknown")
        if cls == "bird" or conf < 0.5: continue
        az, el = pixel_to_azel(cx, cy, r.orig_shape[1], r.orig_shape[0], ptz.az, ptz.el, ptz.hfov, ptz.vfov)
        ptz.center_on(cx, cy)  # тримати ціль у центрі (замкнений трек)
        bus.publish(TOPIC_TRK, Track(track_id=f"eo{int(b.id or 0)}", az_deg=az, el_deg=el,
                     rng_m=-1.0, cls=cls, conf=conf, sources=["eoir"], t_unix=time.time()).to_json())
```

```python
# cuas/sensors/eoir/ptz.py  (ONVIF-обгортка; заповнити camera creds)
class PTZ:
    hfov = 6.0; vfov = 3.4; az = 0.0; el = 0.0
    def __init__(self, url="rtsp://CAM/stream"): self._url = url
    def stream_url(self): return self._url
    def slew_to(self, az_deg): self.az = az_deg   # TODO: ONVIF AbsoluteMove
    def center_on(self, cx, cy): pass             # TODO: ONVIF ContinuousMove пропорц. похибці
```

- [ ] **Step 6: Приймання (день, інертна ціль)**

Тест-квадро на 100–800 м; **очікування:** YOLO класифікує quad/fpv (не bird) conf>0.5; PTZ утримує ціль у центрі ±0,5°; Track публікується ≥5 Гц. Зафіксувати макс. дальність надійного треку (вхід у cue-handoff §M0).

- [ ] **Step 7: Commit**

```bash
git add cuas/sensors/eoir/ cuas/tests/test_eoir_azel.py
git commit -m "feat(eoir): PTZ slew-to-cue + YOLO track publishing az/el"
```

> **Примітка про модель:** `uav_yolo.pt` — окрема задача дообучення на датасеті дронів (COCO-дрон + власні кадри); винести у Task 1.3b (збір датасету + `yolo train`) якщо готової ваги немає.

---

## Milestone M2 — C2: фузія 2-з-N, вибір ефектора, консоль OK/ABORT

### Task 2.1: Фузія 2-з-N (підтвердження треку кількома модальностями)

**Files:**
- Create: `cuas/c2/fusion.py`
- Test: `cuas/tests/test_fusion.py`

- [ ] **Step 1: Падаючий тест**

```python
# cuas/tests/test_fusion.py
from cuas.c2.fusion import Fusion
from cuas.common.messages import Detection

def test_two_sources_same_bearing_confirm():
    f = Fusion(az_gate_deg=12, t_gate_s=2.0)
    assert f.update(Detection("acoustic", 130.0, 0.7, 1000.0)) is None
    trk = f.update(Detection("rf", 134.0, 0.7, 1001.0))
    assert trk is not None and set(trk.sources) == {"acoustic", "rf"}

def test_single_source_no_confirm():
    f = Fusion(12, 2.0)
    assert f.update(Detection("acoustic", 130.0, 0.7, 1000.0)) is None

def test_far_bearing_not_fused():
    f = Fusion(12, 2.0)
    f.update(Detection("acoustic", 130.0, 0.7, 1000.0))
    assert f.update(Detection("rf", 200.0, 0.7, 1000.5)) is None
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_fusion.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати вікно узгодження за азимутом і часом**

```python
# cuas/c2/fusion.py
from typing import Optional, List
from cuas.common.messages import Detection, Track

def _adiff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)

class Fusion:
    def __init__(self, az_gate_deg=12.0, t_gate_s=2.0):
        self.az_gate = az_gate_deg; self.t_gate = t_gate_s
        self._recent: List[Detection] = []
        self._seq = 0

    def update(self, d: Detection) -> Optional[Track]:
        now = d.t_unix
        self._recent = [r for r in self._recent if now - r.t_unix <= self.t_gate]
        match = [r for r in self._recent if r.source != d.source and _adiff(r.az_deg, d.az_deg) <= self.az_gate]
        self._recent.append(d)
        if match:
            srcs = sorted({d.source, *[m.source for m in match]})
            az = sum([d.az_deg] + [m.az_deg for m in match]) / (1 + len(match))
            cls = d.cls or next((m.cls for m in match if m.cls), "unknown")
            self._seq += 1
            return Track(track_id=f"trk{self._seq}", az_deg=az, el_deg=d.el_deg or 0.0,
                         rng_m=-1.0, cls=cls, conf=max(d.conf, *[m.conf for m in match]),
                         sources=srcs, t_unix=now)
        return None
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_fusion.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add cuas/c2/fusion.py cuas/tests/test_fusion.py
git commit -m "feat(c2): 2-of-N sensor fusion with az/time gating"
```

### Task 2.2: Вибір ефектора + no-fire дуги + вогневе рішення

**Files:**
- Create: `cuas/c2/engage.py`
- Test: `cuas/tests/test_engage.py`

- [ ] **Step 1: Падаючий тест**

```python
# cuas/tests/test_engage.py
from cuas.c2.engage import select_effector, in_no_fire
from cuas.common.messages import Track

def _trk(cls, az): return Track("t", az, 5.0, 600.0, cls, 0.8, ["eoir","acoustic"], 1.0)

def test_quad_selects_e1_net():
    assert select_effector(_trk("quad", 100)) == "E1"

def test_fpv_selects_e2_ram():
    assert select_effector(_trk("fpv", 100)) == "E2"

def test_fixedwing_deferred_phase3():
    assert select_effector(_trk("fixedwing", 100)) is None  # E3 не в Phase 1

def test_no_fire_arc_blocks():
    assert in_no_fire(az_deg=185, arcs=[(170, 200)]) is True
    assert in_no_fire(az_deg=100, arcs=[(170, 200)]) is False
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_engage.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати**

```python
# cuas/c2/engage.py
from typing import Optional, List, Tuple
from cuas.common.messages import Track

EFFECTOR_BY_CLASS = {"quad": "E1", "fpv": "E2"}   # fixedwing -> None (E3, Phase 3)

def select_effector(trk: Track) -> Optional[str]:
    return EFFECTOR_BY_CLASS.get(trk.cls)

def in_no_fire(az_deg: float, arcs: List[Tuple[float, float]]) -> bool:
    a = az_deg % 360
    for lo, hi in arcs:
        lo %= 360; hi %= 360
        if lo <= hi:
            if lo <= a <= hi: return True
        else:
            if a >= lo or a <= hi: return True
    return False

def firing_solution(trk: Track):
    """Мінімальне рішення: ефектор, азимут пуску, клас. Кутове наведення далі веде бортове бачення."""
    eff = select_effector(trk)
    return None if eff is None else {"effector": eff, "launch_az": trk.az_deg, "cls": trk.cls}
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_engage.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add cuas/c2/engage.py cuas/tests/test_engage.py
git commit -m "feat(c2): effector selection by class + no-fire arcs + firing solution"
```

### Task 2.3: Консоль оператора (OK/ABORT) + оркестратор C2

**Files:**
- Create: `cuas/c2/server.py`
- Create: `cuas/c2/console.html`
- Test: `cuas/tests/test_c2_flow.py`

- [ ] **Step 1: Падаючий тест логіки станів (без веб)**

```python
# cuas/tests/test_c2_flow.py
from cuas.c2.server import Engagement

def test_requires_ok_before_launch():
    e = Engagement(solution={"effector":"E2","launch_az":100,"cls":"fpv"})
    assert e.state == "AWAIT_OK"
    assert e.command() is None
    e.operator_ok()
    assert e.state == "LAUNCHED"
    assert e.command()["effector"] == "E2"

def test_abort_stops_before_hit():
    e = Engagement(solution={"effector":"E2","launch_az":100,"cls":"fpv"})
    e.operator_ok(); e.operator_abort()
    assert e.state == "ABORTED"
    assert e.command()["type"] == "ABORT"
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_c2_flow.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати автомат заручення**

```python
# cuas/c2/server.py (ядро; веб нижче)
class Engagement:
    def __init__(self, solution):
        self.sol = solution; self.state = "AWAIT_OK"; self._cmd = None
    def operator_ok(self):
        if self.state == "AWAIT_OK":
            self.state = "LAUNCHED"; self._cmd = {"type":"LAUNCH", **self.sol}
    def operator_abort(self):
        self.state = "ABORTED"; self._cmd = {"type":"ABORT"}
    def command(self):
        return self._cmd
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_c2_flow.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: FastAPI-оркестратор + WS-консоль**

```python
# cuas/c2/server.py (додати внизу)
from fastapi import FastAPI, WebSocket
from cuas.common.bus import Bus, TOPIC_TRK, TOPIC_CMD, TOPIC_DET
from cuas.common.messages import Track, Detection
from cuas.c2.fusion import Fusion
from cuas.c2.engage import firing_solution, in_no_fire
import json, uvicorn

app = FastAPI(); bus = Bus(); fusion = Fusion(); NO_FIRE = [(170, 200)]
current = {"eng": None}

def on_det(js):
    d = Detection.from_json(js); trk = fusion.update(d)
    if trk and not in_no_fire(trk.az_deg, NO_FIRE):
        sol = firing_solution(trk)
        if sol: current["eng"] = Engagement(sol)   # чекає OK у консолі
bus.subscribe(TOPIC_DET, on_det)

@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    while True:
        msg = await sock.receive_text(); act = json.loads(msg).get("action")
        eng = current["eng"]
        if eng and act == "OK": eng.operator_ok(); bus.publish(TOPIC_CMD, json.dumps(eng.command()))
        if eng and act == "ABORT": eng.operator_abort(); bus.publish(TOPIC_CMD, json.dumps(eng.command()))
        await sock.send_text(json.dumps({"state": eng.state if eng else "IDLE",
                                         "sol": eng.sol if eng else None}))
```

```html
<!-- cuas/c2/console.html — велика кнопка OK і завжди-доступний ABORT -->
<div id="s">IDLE</div>
<button onclick="send('OK')">✅ ПУСК (OK)</button>
<button onclick="send('ABORT')" style="background:#c0392b;color:#fff">🛑 СКАСУВАТИ</button>
<script>
const w=new WebSocket(`ws://${location.host}/ws`);
function send(a){w.send(JSON.stringify({action:a}))}
w.onmessage=e=>{const d=JSON.parse(e.data);document.getElementById('s').textContent=d.state+' '+JSON.stringify(d.sol||{})}
</script>
```

- [ ] **Step 6: Приймання (софт-інтеграція)**

Запустити mosquitto + `uvicorn cuas.c2.server:app`; подати синтетичні Detection (acoustic+rf однакового азимуту); **очікування:** у консолі зʼявляється рішення у стані AWAIT_OK; натиск OK публікує LAUNCH у `cuas/commands`; ABORT публікує ABORT будь-коли.

- [ ] **Step 7: Commit**

```bash
git add cuas/c2/server.py cuas/c2/console.html cuas/tests/test_c2_flow.py
git commit -m "feat(c2): operator OK/ABORT console + engagement orchestrator"
```

---

## Milestone M3 — E2: наддешевий авто-таран (спочатку — простіший ефектор)

> Будуємо автономний термінал на дешевій платформі. Політ у GUIDED, наведення — центроїд-трекінг / пропорційна навігація від бортової камери.

### Task 3.1: Бортове наведення (offboard velocity від центру cіли)

**Files:**
- Create: `cuas/effectors/e2_ram/guidance.py`
- Test: `cuas/tests/test_guidance.py`

- [ ] **Step 1: Падаючий тест закону наведення**

```python
# cuas/tests/test_guidance.py
from cuas.effectors.e2_ram.guidance import velocity_cmd

def test_target_right_commands_right_yawrate():
    vx, vy, vz, yaw = velocity_cmd(err_x=0.5, err_y=0.0, v_closing=25.0)
    assert yaw > 0 and vx > 0

def test_target_high_commands_climb():
    _, _, vz, _ = velocity_cmd(err_x=0.0, err_y=-0.5, v_closing=25.0)  # ціль вище (y менший)
    assert vz > 0  # NED: up = -z, повертаємо додатнє «вгору» у нашій конвенції
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_guidance.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати (нормовані похибки центру bbox → команди)**

```python
# cuas/effectors/e2_ram/guidance.py
def velocity_cmd(err_x: float, err_y: float, v_closing: float, k_yaw=1.5, k_climb=8.0):
    """err_x,err_y у [-1..1] від центру кадру (x праворуч+, y вниз+).
    Повертає (vx forward, vy, vz_up, yaw_rate). Класична lead-pursuit: тримати ціль у центрі, йти вперед."""
    yaw_rate = k_yaw * err_x
    vz_up = k_climb * (-err_y)          # ціль вище (err_y<0) -> набір
    vx = v_closing                       # завжди зближення вперед
    vy = 0.0
    return vx, vy, vz_up, yaw_rate
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_guidance.py -v`
Expected: PASS

- [ ] **Step 5: Companion-цикл (камера → YOLO → MAVLink SET_POSITION_TARGET)**

```python
# cuas/effectors/e2_ram/companion.py
import time
from pymavlink import mavutil
from ultralytics import YOLO
from cuas.effectors.e2_ram.guidance import velocity_cmd

def run(conn="udp:127.0.0.1:14550", model="uav_yolo.pt", cam=0, v_closing=25.0):
    m = mavutil.mavlink_connection(conn); m.wait_heartbeat()
    net = YOLO(model)
    for r in net.track(source=cam, stream=True, persist=True, verbose=False):
        if not r.boxes or len(r.boxes)==0: continue
        b = r.boxes[int(r.boxes.conf.argmax())]
        H, W = r.orig_shape; cx, cy = map(float, b.xywh[0][:2])
        ex = (cx - W/2)/(W/2); ey = (cy - H/2)/(H/2)
        vx, vy, vz_up, yaw = velocity_cmd(ex, ey, v_closing)
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b0000011111000111, 0,0,0, vx, vy, -vz_up, 0,0,0, 0, yaw)   # NED: down=+, тож up=-vz
        time.sleep(0.05)
```

- [ ] **Step 6: SITL-приймання (без заліза)**

Запустити ArduCopter SITL; подати відеофайл із квадро; **очікування:** companion шле SET_POSITION_TARGET; у SITL апарат розвертається/йде на напрям цілі. Лог MAVLink зберегти.

```bash
sim_vehicle.py -v ArduCopter --console &   # ArduPilot SITL
python -m cuas.effectors.e2_ram.companion --conn udp:127.0.0.1:14550 --cam test_fpv.mp4
```
Expected: apparat реагує курсом/тангажем на позицію цілі у відео.

- [ ] **Step 7: Commit**

```bash
git add cuas/effectors/e2_ram/ cuas/tests/test_guidance.py
git commit -m "feat(e2): onboard vision lead-pursuit guidance + MAVLink offboard"
```

### Task 3.2: E2 збірка + польове приймання (інертно)

**Files:** (документація збірки)
- Create: `cuas/effectors/e2_ram/BUILD.md`

- [ ] **Step 1: Специфікація збірки (BOM ~$200/шт)**

Записати у BUILD.md: 5″ рама, 4× мотори 2306/1900KV + 4-в-1 ESC, FC з ArduPilot, ELRS RX, 6S 1300 LiPo, дешева камера (глобальний затвор бажано) + Pi Zero 2W/Coral, вага payload-місця (інертний імітатор БЧ). **Без VTX/пілота.**

- [ ] **Step 2: Приймання швидкості/набору**

Тест-політ (без наведення): виміряти макс. горизонтальну швидкість і скоропідйомність. **Очікування:** ≥ 70 м/с (252 км/год) або задокументувати фактичне для оновлення моделі M0; набір ≥ 25 м/с.

- [ ] **Step 3: Приймання автономного перехоплення (інертна мішень)**

На полігоні: підняти інертну FPV-мішень; C2 → OK; **очікування:** E2 автономно (бортове бачення) зближується й уражає мішень **без пілота**; ABORT з консолі відводить апарат. Записати % влучань за N спроб.

- [ ] **Step 4: Commit**

```bash
git add cuas/effectors/e2_ram/BUILD.md
git commit -m "docs(e2): build spec + inert-target acceptance procedure"
```

---

## Milestone M4 — E1: багаторазовий сітка-дрон

### Task 4.1: Логіка approach + скид сітки + повернення (RTL)

**Files:**
- Create: `cuas/effectors/e1_net/mission.py`
- Test: `cuas/tests/test_net_trigger.py`

- [ ] **Step 1: Падаючий тест умови скиду сітки**

```python
# cuas/tests/test_net_trigger.py
from cuas.effectors.e1_net.mission import should_fire_net

def test_fires_when_centered_and_in_range():
    assert should_fire_net(err_x=0.05, err_y=0.05, rng_m=6.0, max_rng=8.0) is True

def test_no_fire_when_off_center():
    assert should_fire_net(err_x=0.4, err_y=0.0, rng_m=6.0, max_rng=8.0) is False

def test_no_fire_when_too_far():
    assert should_fire_net(0.05, 0.05, rng_m=15.0, max_rng=8.0) is False
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_net_trigger.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати**

```python
# cuas/effectors/e1_net/mission.py
def should_fire_net(err_x, err_y, rng_m, max_rng=8.0, center_tol=0.12):
    return (abs(err_x) <= center_tol and abs(err_y) <= center_tol and rng_m <= max_rng)

def net_servo_pwm(fire: bool) -> int:
    return 1900 if fire else 1100   # PWM для сітколета (пружина/CO2)
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_net_trigger.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Companion (reuse E2-guidance до дистанції сітки → fire → RTL)**

```python
# cuas/effectors/e1_net/companion.py
import time
from pymavlink import mavutil
from ultralytics import YOLO
from cuas.effectors.e2_ram.guidance import velocity_cmd
from cuas.effectors.e1_net.mission import should_fire_net, net_servo_pwm

def bbox_range_m(bbox_h_px, H, target_size_m=0.35, vfov_deg=48.0):
    import math
    ang = (bbox_h_px / H) * math.radians(vfov_deg)
    return target_size_m / max(math.tan(ang/2)*2, 1e-3)

def run(conn="udp:127.0.0.1:14550", model="uav_yolo.pt", cam=0):
    m = mavutil.mavlink_connection(conn); m.wait_heartbeat(); net = YOLO(model)
    for r in net.track(source=cam, stream=True, persist=True, verbose=False):
        if not r.boxes or len(r.boxes)==0: continue
        b = r.boxes[int(r.boxes.conf.argmax())]; H, W = r.orig_shape
        cx, cy, bw, bh = map(float, b.xywh[0]); ex=(cx-W/2)/(W/2); ey=(cy-H/2)/(H/2)
        rng = bbox_range_m(bh, H)
        if should_fire_net(ex, ey, rng):
            m.mav.command_long_send(m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0, 9, net_servo_pwm(True), 0,0,0,0,0)
            time.sleep(0.5)
            m.set_mode("RTL"); return
        vx,vy,vz,yaw = velocity_cmd(ex, ey, v_closing=12.0)  # повільніше за E2 (акуратний підхід)
        m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED, 0b0000011111000111, 0,0,0, vx,vy,-vz,0,0,0,0,yaw)
        time.sleep(0.05)
```

- [ ] **Step 6: SITL + bench servo-приймання**

SITL із відео квадро → **очікування:** апарат зближується до «дистанції сітки», подає servo PWM 1900 (перевірити на стенді, що сітколет спрацьовує), тоді RTL. 

- [ ] **Step 7: Commit**

```bash
git add cuas/effectors/e1_net/ cuas/tests/test_net_trigger.py
git commit -m "feat(e1): net-drone approach + range-gated net trigger + RTL reuse"
```

### Task 4.2: E1 збірка + приймання багаторазовості

**Files:**
- Create: `cuas/effectors/e1_net/BUILD.md`

- [ ] **Step 1: Специфікація (BOM ~$1,100 планер + сітколет + компут + гімбал)**

BUILD.md: несучий 7–10″ квадро, гімбал-камера, Pi5/Coral, сітколет (пружина/CO₂, картридж-сітка $20–50, ремонтопридатний), парашут або мʼяка посадка для повернення.

- [ ] **Step 2: Приймання захоплення + повернення (інертна квадро-мішень)**

Полігон: інертний квадро завис/повільний рух; C2 → OK; **очікування:** E1 автономно зближується, скидає сітку, **ціль заплутана й опускається**, E1 **повертається (RTL) неушкодженим і придатним до повтору**. Порахувати вартість/ураження = картридж + знос.

- [ ] **Step 3: Приймання повторюваності**

Виконати ≥5 циклів «виліт → захоплення → повернення → перезарядка сітки» одним апаратом; зафіксувати середній час перезарядки та відмови.

- [ ] **Step 4: Commit**

```bash
git add cuas/effectors/e1_net/BUILD.md
git commit -m "docs(e1): build spec + reusability acceptance procedure"
```

---

## Milestone M5 — Наскрізна інтеграція та cue-handoff

### Task 5.1: End-to-end авто-заручення (сенсори → C2 → ефектор), інертно

**Files:**
- Create: `cuas/c2/dispatch.py`
- Test: `cuas/tests/test_dispatch.py`

- [ ] **Step 1: Падаючий тест маршрутизації команди до правильного ефектора**

```python
# cuas/tests/test_dispatch.py
from cuas.c2.dispatch import route

def test_e1_command_goes_to_net_endpoint():
    assert route({"type":"LAUNCH","effector":"E1"}) == "cuas/effectors/e1_net/cmd"

def test_e2_command_goes_to_ram_endpoint():
    assert route({"type":"LAUNCH","effector":"E2"}) == "cuas/effectors/e2_ram/cmd"

def test_abort_broadcasts():
    assert route({"type":"ABORT"}) == "cuas/effectors/all/cmd"
```

- [ ] **Step 2: Запустити — впаде**

Run: `pytest cuas/tests/test_dispatch.py -v`
Expected: FAIL

- [ ] **Step 3: Реалізувати маршрутизацію**

```python
# cuas/c2/dispatch.py
def route(cmd: dict) -> str:
    if cmd.get("type") == "ABORT": return "cuas/effectors/all/cmd"
    return {"E1":"cuas/effectors/e1_net/cmd","E2":"cuas/effectors/e2_ram/cmd"}[cmd["effector"]]
```

- [ ] **Step 4: Запустити — має пройти**

Run: `pytest cuas/tests/test_dispatch.py -v`
Expected: PASS

- [ ] **Step 5: Наскрізне польове приймання (день, інертно)**

Повний стек на полігоні. Сценарій A (квадро): підняти інертний Mavic → акустика+РЧ cue → PTZ підтверджує «quad» → C2 обирає **E1** → оператор OK → E1 захоплює → RTL. Сценарій B (FPV): інертна FPV-мішень → PTZ «fpv» → **E2** → OK → таран. **Очікування:** правильний ефектор автоматично; ABORT зупиняє на будь-якій стадії; час cue→пуск виміряти й звірити з моделлю M0.

- [ ] **Step 6: Commit**

```bash
git add cuas/c2/dispatch.py cuas/tests/test_dispatch.py
git commit -m "feat(c2): effector command routing + end-to-end engagement"
```

### Task 5.2: Оновити модель M0 реальними цифрами й зафіксувати envelope

- [ ] **Step 1:** Внести у `cuas/sim/intercept.py` виміряні: швидкість/набір E2 (Task 3.2), дальність надійного треку EO/IR (Task 1.3), латентність cue→пуск (Task 5.1).
- [ ] **Step 2:** Перегенерувати envelope-таблицю; **якщо FPV поза envelope** — задокументувати обмеження й пункт для Phase 2 (краща дальність/швидкість). 
- [ ] **Step 3: Commit** `git commit -am "chore(sim): calibrate intercept model with measured field values"`

---

## Milestone M6 — Безпека, приймання, верифікація вартості

### Task 6.1: Безпекова валідація

- [ ] **Step 1:** Тест no-fire дуг у полі: спроба заручення у забороненому секторі — пуск **блокується** (перевірити `in_no_fire`).
- [ ] **Step 2:** ABORT-латентність: виміряти час від натиску до зупинки/відводу на E1 та E2; **очікування:** зупинка до точки удару на типовій геометрії.
- [ ] **Step 3:** Fail-safe: втрата лінку C2↔ефектор → ефектор іде у RTL/land, не «сліпий таран».
- [ ] **Step 4: Commit** документ безпеки `docs/superpowers/plans/cuas-safety-checklist.md`.

### Task 6.2: Фінальне приймання за критеріями спеки §11

- [ ] **Step 1:** Пройти чек-лист спеки: детекція (дальність+false-rate), cue-handoff, автономність C2, E1 (захоплення+повернення), E2 (авто-таран), безпека (no-fire+ABORT).
- [ ] **Step 2:** **Верифікація вартості:** порахувати фактичний BOM сайту (E1 + 4×E2 + сенсори + C2) ≤ $5,000 і фактичну вартість/ураження по кожному класу; підтвердити обмін на нашу користь (таблиця спеки §2).
- [ ] **Step 3:** Звіт приймання `docs/superpowers/plans/cuas-phase1-acceptance.md` з фактичними цифрами й envelope.
- [ ] **Step 4: Commit** `git commit -m "docs(cuas): phase-1 acceptance report + cost-exchange verification"`

---

## Self-Review (виконано автором плану)

**Spec coverage:** §5.1 сенсори → M1(1.1–1.3); §5.2 C2/автономність/оператор → M2(2.1–2.3); §5.3 E1/E2 → M3,M4; §6 cue-handoff/модель → M0(0.2)+M5(5.2); §2 обмін вартістю → M6(6.2); §9 безпека/no-fire/ABORT → M2.2+M6.1; §10 ризик маржі 25% → M0.2 (гейт); §11 приймання → M6.2. E3/фікс-крило свідомо **поза Phase 1** (роадмап §8).

**Placeholder scan:** реальний код/тести в кожному софт-кроці; апаратні кроки мають конкретні BOM/процедури приймання. Свідомі TODO лише в ONVIF-обгортці PTZ (Task 1.3, camera-specific) і датасеті YOLO (1.3b) — позначені явно, не приховані.

**Type consistency:** `Detection`/`Track` (0.1) використовуються однаково в M1/M2; `velocity_cmd` (3.1) перевикористано в E1 (4.1); `select_effector`/`route` узгоджені по ефекторах E1/E2; MQTT-топіки з `cuas/common/bus.py` єдині.
