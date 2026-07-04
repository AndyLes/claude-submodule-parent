from dataclasses import dataclass, asdict
from typing import List, Optional
import json

@dataclass
class Detection:
    source: str
    az_deg: float
    conf: float
    t_unix: float
    el_deg: Optional[float] = None
    freq_mhz: Optional[float] = None
    cls: Optional[str] = None
    def to_json(self) -> str: return json.dumps(asdict(self))
    @classmethod
    def from_json(cls, s: str) -> "Detection": return cls(**json.loads(s))

@dataclass
class Track:
    track_id: str
    az_deg: float
    el_deg: float
    rng_m: float
    cls: str
    conf: float
    sources: List[str]
    t_unix: float
    def to_json(self) -> str: return json.dumps(asdict(self))
    @classmethod
    def from_json(cls, s: str) -> "Track": return cls(**json.loads(s))
