from typing import Optional, List
from cuas.common.messages import Detection, Track


def _adiff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


class Fusion:
    """Підтвердження треку кількома модальностями у вікні за азимутом і часом (2-з-N)."""

    def __init__(self, az_gate_deg=12.0, t_gate_s=2.0):
        self.az_gate = az_gate_deg
        self.t_gate = t_gate_s
        self._recent: List[Detection] = []
        self._seq = 0

    def update(self, d: Detection) -> Optional[Track]:
        now = d.t_unix
        self._recent = [r for r in self._recent if now - r.t_unix <= self.t_gate]
        match = [r for r in self._recent
                 if r.source != d.source and _adiff(r.az_deg, d.az_deg) <= self.az_gate]
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
