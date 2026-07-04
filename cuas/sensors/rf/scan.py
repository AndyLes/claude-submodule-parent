import numpy as np


def detect_drone_band(freqs, psd_db, floor_db=-90.0, min_bw_hz=10e6):
    """Знайти суцільний сегмент PSD над floor завширшки >= min_bw (DJI OcuSync ~10-40 МГц)."""
    above = psd_db > floor_db
    if not above.any():
        return None
    df = float(freqs[1] - freqs[0])
    best = None
    i = 0
    n = len(above)
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            bw = (j - i) * df
            if bw >= min_bw_hz:
                seg = slice(i, j)
                cand = {
                    "center_hz": float(freqs[seg].mean()),
                    "bw_hz": float(bw),
                    "peak_db": float(psd_db[seg].max()),
                }
                if best is None or cand["peak_db"] > best["peak_db"]:
                    best = cand
            i = j
        else:
            i += 1
    return best
