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
