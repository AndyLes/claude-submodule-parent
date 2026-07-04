import numpy as np
from cuas.sensors.acoustic.classify import drone_score


def test_tonal_bpf_signature_scores_high():
    sr = 16000
    t = np.arange(sr) / sr
    # дрон: набір гармонік лопатевої частоти ~110 Гц + гармоніки
    sig = sum(np.sin(2 * np.pi * 110 * k * t) for k in range(1, 8)).astype(np.float32)
    assert drone_score(sig, sr) > 0.6


def test_white_noise_scores_low():
    rng = np.random.default_rng(0)
    assert drone_score(rng.standard_normal(16000).astype(np.float32), 16000) < 0.4
