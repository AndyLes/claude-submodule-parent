import numpy as np
from cuas.sensors.rf.scan import detect_drone_band


def test_detects_20mhz_bump_in_2p4():
    freqs = np.linspace(2400e6, 2483e6, 4096)
    psd = np.full_like(freqs, -95.0)
    center = np.argmin(np.abs(freqs - 2437e6))
    psd[center - 500:center + 500] += 25.0   # ~20 МГц «горб» -70 дБ (df≈20 кГц × 1000 бінів)
    hit = detect_drone_band(freqs, psd, floor_db=-90, min_bw_hz=10e6)
    assert hit is not None and abs(hit["center_hz"] - 2437e6) < 5e6


def test_no_hit_on_flat_floor():
    freqs = np.linspace(2400e6, 2483e6, 4096)
    assert detect_drone_band(freqs, np.full_like(freqs, -95.0), -90, 10e6) is None
