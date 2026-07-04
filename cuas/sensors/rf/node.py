import time

from cuas.common.bus import Bus, TOPIC_DET
from cuas.common.messages import Detection
from cuas.sensors.rf.scan import detect_drone_band


def run(get_bearing_deg, centers=(2437e6, 5800e6), fs=2.4e6):
    # lazy: hardware/heavy deps, only needed when the daemon runs
    import numpy as np
    from rtlsdr import RtlSdr
    from scipy.signal import welch

    sdr = RtlSdr()
    sdr.sample_rate = fs
    bus = Bus()
    while True:
        for fc in centers:
            sdr.center_freq = fc
            iq = sdr.read_samples(256 * 1024)
            f, p = welch(iq, fs=fs, nperseg=4096, return_onesided=False)
            f = np.fft.fftshift(f) + fc
            p = 10 * np.log10(np.fft.fftshift(p) + 1e-12)
            hit = detect_drone_band(f, p, floor_db=np.median(p) + 12, min_bw_hz=8e6)
            if hit:
                bus.publish(
                    TOPIC_DET,
                    Detection(source="rf", az_deg=get_bearing_deg(), conf=0.7,
                              t_unix=time.time(), freq_mhz=hit["center_hz"] / 1e6).to_json(),
                )
